import base64
import os
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from app.config import settings
from app.core.logging import logger

class OpenRouterClient:
    def __init__(self):
        self.base_url = settings.OPENROUTER_BASE_URL
        self.api_key = settings.OPENROUTER_API_KEY
        self.model_name = settings.MODEL_NAME
        self._semaphore = None
        logger.info(f"AI Client (OpenRouter) initialized with base_url: {self.base_url}, model: {self.model_name}")

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            # Enforce maximum 3 concurrent requests to OpenRouter
            self._semaphore = asyncio.Semaphore(3)
        return self._semaphore

    def _encode_image(self, image_path: str) -> str:
        """Helper to convert image to base64 string."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def generate_chat(
        self,
        prompt: str,
        image_paths: Optional[List[str]] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        model_name: Optional[str] = None
    ) -> str:
        """
        Sends a query to OpenRouter chat completions endpoint.
        Optionally accepts a list of local image paths for multimodal queries.
        """
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        
        # Force strict JSON output behavior
        final_prompt = prompt
        if json_mode:
            final_prompt += "\n\nCRITICAL INSTRUCTION: You MUST output ONLY valid JSON. Do not include any conversational text, explanations, or markdown formatting outside the JSON block. Your response must start with '{' or '[' and end with '}' or ']'."
            
        # Prepare the message content
        content_parts = [{"type": "text", "text": final_prompt}]
        if image_paths:
            for path in image_paths:
                try:
                    if path.startswith("http://") or path.startswith("https://"):
                        # If it's a Cloudinary URL, inject transformations to prevent OpenRouter OOM (CUDA Out Of Memory)
                        # We limit width/height to 1400px and auto-compress quality/format.
                        optimized_url = path
                        if "res.cloudinary.com" in path and "/upload/" in path:
                            optimized_url = path.replace("/upload/", "/upload/c_limit,w_1400,h_1400,q_auto,f_auto/")
                        content_parts.append({"type": "image_url", "image_url": {"url": optimized_url}})
                    elif path.startswith("data:image/"):
                        # Direct base64 data URL, append as-is
                        content_parts.append({"type": "image_url", "image_url": {"url": path}})
                    else:
                        b64 = self._encode_image(path)
                        ext = os.path.splitext(path)[1].lower().strip(".")
                        mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
                        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{b64}"}})
                except Exception as e:
                    logger.error(f"Failed to encode image {path[:100]}...: {e}")
                    raise e
                    
        payload = {
            "model": model_name or self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": content_parts
                }
            ],
            "stream": False,
            "temperature": temperature,
            "max_tokens": 8192
        }
        
        if json_mode:
            # We don't send response_format={"type": "json_object"} because 
            # many open-source models (like Qwen) fail or return empty responses.
            # We rely on the prompt instructions and our robust parse_json_response fallback.
            pass
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:3000", # Required by OpenRouter
            "X-Title": "Costmate", # Optional identifier for OpenRouter
            "Accept": "application/json"
        }
            
        logger.info(f"Sending request to OpenRouter: {url} (multimodal={bool(image_paths)}, json_mode={json_mode})")
        
        # 180s read timeout for multimodal vision models
        timeout = httpx.Timeout(180.0, connect=30.0)
        
        # Acquire global semaphore before executing HTTP request
        async with self._get_semaphore():
            async with httpx.AsyncClient(timeout=timeout) as client:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.post(url, headers=headers, json=payload)
                        response.raise_for_status()
                        result = response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if not content and attempt < max_retries - 1:
                            logger.warning(f"Received empty response from OpenRouter (Attempt {attempt+1}/{max_retries}). Retrying in 2 seconds...")
                            await asyncio.sleep(2)
                            continue
                            
                        return content
                    except httpx.HTTPStatusError as e:
                        if (e.response.status_code >= 500 or e.response.status_code == 429) and attempt < max_retries - 1:
                            logger.warning(f"Rate limit or 5xx error from OpenRouter (Attempt {attempt+1}/{max_retries}): {e.response.status_code}. Retrying in 4 seconds...")
                            await asyncio.sleep(4)
                            continue
                        logger.error(f"HTTP status error from OpenRouter: {e.response.status_code} - {e.response.text}")
                        raise e
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Connection error to OpenRouter (Attempt {attempt+1}/{max_retries}): {e}. Retrying in 2 seconds...")
                            await asyncio.sleep(2)
                            continue
                        logger.error(f"Error during API request: {e}")
                        raise e

# Global singleton client
openrouter_client = OpenRouterClient()

def parse_json_response(text: str) -> dict:
    """Safely cleans and parses JSON from LLM responses, removing markdown wrappers if present."""
    import json
    import re
    
    if not text:
        raise ValueError("Received empty response from the vision model.")
        
    cleaned = text.strip()
    
    # Try to find a markdown json block anywhere in the text first
    md_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if md_match:
        try:
            return json.loads(md_match.group(1))
        except Exception:
            pass
            
    # Remove markdown code block wrappers if they wrap the entire text
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()
        
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Fallback: extract the largest JSON object or array using regex
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        raise ValueError(f"Failed to parse JSON from OpenRouter response: {text[:300]}... (Error: {e})")
