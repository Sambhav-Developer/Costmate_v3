import base64
import os
import httpx
import asyncio
import random
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from app.config import settings
from app.core.logging import logger

@dataclass
class OpenRouterMetrics:
    total_requests: int = 0
    total_successful_requests: int = 0
    total_429_hits: int = 0
    total_retries: int = 0
    total_exhausted_failures: int = 0
    total_5xx_hits: int = 0
    peak_in_flight: int = 0

    def reset(self):
        self.total_requests = 0
        self.total_successful_requests = 0
        self.total_429_hits = 0
        self.total_retries = 0
        self.total_exhausted_failures = 0
        self.total_5xx_hits = 0
        self.peak_in_flight = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_requests": self.total_requests,
            "total_successful_requests": self.total_successful_requests,
            "total_429_hits": self.total_429_hits,
            "total_retries": self.total_retries,
            "total_exhausted_failures": self.total_exhausted_failures,
            "total_5xx_hits": self.total_5xx_hits,
            "peak_in_flight": self.peak_in_flight,
        }

class OpenRouterClient:
    def __init__(self):
        self.base_url = settings.OPENROUTER_BASE_URL
        self.api_key = settings.OPENROUTER_API_KEY
        self.model_name = settings.MODEL_NAME
        self._semaphore = None
        self._semaphore_limit = None
        self._in_flight = 0
        self.metrics = OpenRouterMetrics()
        logger.info(f"AI Client (OpenRouter) initialized with base_url: {self.base_url}, model: {self.model_name}")

    def _get_semaphore(self) -> asyncio.Semaphore:
        limit = getattr(settings, "OPENROUTER_CONCURRENCY_LIMIT", 3)
        if self._semaphore is None or self._semaphore_limit != limit:
            self._semaphore_limit = limit
            self._semaphore = asyncio.Semaphore(limit)
        return self._semaphore

    def _parse_retry_after(self, response: httpx.Response) -> Optional[float]:
        """Parses the Retry-After header if present (supports integer seconds or HTTP date format)."""
        if not response or not hasattr(response, "headers"):
            return None
        header_val = response.headers.get("retry-after") or response.headers.get("Retry-After")
        if not header_val:
            return None
            
        header_clean = str(header_val).strip()
        try:
            # Try float/integer seconds first
            return float(header_clean)
        except ValueError:
            pass
            
        try:
            # Try HTTP-date format (e.g. 'Wed, 21 Oct 2026 07:28:00 GMT')
            target_dt = parsedate_to_datetime(header_clean)
            now_dt = datetime.now(timezone.utc)
            delta = (target_dt - now_dt).total_seconds()
            return max(0.0, delta)
        except Exception:
            return None

    def _calculate_backoff_delay(self, attempt: int, retry_after_seconds: Optional[float] = None) -> float:
        """Calculates exponential backoff delay with random jitter and Retry-After header enforcement."""
        base_delay = getattr(settings, "OPENROUTER_BASE_BACKOFF_SECONDS", 1.0)
        max_delay = getattr(settings, "OPENROUTER_MAX_BACKOFF_SECONDS", 30.0)
        jitter_ratio = getattr(settings, "OPENROUTER_JITTER_RATIO", 0.2)

        exp_delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        if retry_after_seconds is not None and retry_after_seconds > 0:
            delay = max(retry_after_seconds, exp_delay)
        else:
            delay = exp_delay

        jitter = delay * random.uniform(-jitter_ratio, +jitter_ratio)
        return max(0.1, round(delay + jitter, 3))

    def _encode_image(self, image_path: str) -> str:
        """Helper to convert image to base64 string."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Surfaces run metrics for rate-limit monitoring and logging."""
        return self.metrics.to_dict()

    def reset_metrics(self):
        """Resets per-run rate-limit tracking counters."""
        self.metrics.reset()

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
        Gated by global asyncio.Semaphore bounded concurrency and exponential backoff on HTTP 429.
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
                        # If it's a Cloudinary URL, inject transformations to prevent OpenRouter OOM
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
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Costmate",
            "Accept": "application/json"
        }
            
        logger.info(f"Sending request to OpenRouter: {url} (multimodal={bool(image_paths)}, json_mode={json_mode})")
        
        # 180s read timeout for multimodal vision models
        timeout = httpx.Timeout(180.0, connect=30.0)
        max_retries = getattr(settings, "OPENROUTER_MAX_RETRIES", 5)
        
        self.metrics.total_requests += 1
        
        # Acquire global semaphore before executing HTTP request
        async with self._get_semaphore():
            self._in_flight += 1
            if self._in_flight > self.metrics.peak_in_flight:
                self.metrics.peak_in_flight = self._in_flight
                
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    for attempt in range(1, max_retries + 1):
                        try:
                            response = await client.post(url, headers=headers, json=payload)
                            response.raise_for_status()
                            result = response.json()
                            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                            
                            if not content and attempt < max_retries:
                                delay = self._calculate_backoff_delay(attempt)
                                logger.warning(f"Received empty response from OpenRouter (Attempt {attempt}/{max_retries}). Retrying in {delay:.2f}s...")
                                self.metrics.total_retries += 1
                                await asyncio.sleep(delay)
                                continue
                                
                            self.metrics.total_successful_requests += 1
                            return content

                        except httpx.HTTPStatusError as e:
                            status_code = e.response.status_code
                            if status_code == 429:
                                self.metrics.total_429_hits += 1
                                retry_after = self._parse_retry_after(e.response)
                                delay = self._calculate_backoff_delay(attempt, retry_after)
                                
                                logger.warning(
                                    f"OpenRouter HTTP 429 Rate Limit (Attempt {attempt}/{max_retries}) | "
                                    f"Retry-After: {retry_after}s | Backoff Delay: {delay:.2f}s | Model: {payload['model']}"
                                )
                                
                                if attempt < max_retries:
                                    self.metrics.total_retries += 1
                                    await asyncio.sleep(delay)
                                    continue
                                else:
                                    self.metrics.total_exhausted_failures += 1
                                    logger.error(f"OpenRouter 429 rate limit exhausted after {max_retries} attempts.")
                                    raise e

                            elif status_code >= 500:
                                self.metrics.total_5xx_hits += 1
                                delay = self._calculate_backoff_delay(attempt)
                                logger.warning(
                                    f"OpenRouter 5xx Server Error {status_code} (Attempt {attempt}/{max_retries}). "
                                    f"Retrying in {delay:.2f}s..."
                                )
                                if attempt < max_retries:
                                    self.metrics.total_retries += 1
                                    await asyncio.sleep(delay)
                                    continue
                                else:
                                    self.metrics.total_exhausted_failures += 1
                                    logger.error(f"OpenRouter 5xx server error exhausted after {max_retries} attempts.")
                                    raise e

                            else:
                                # Non-retryable 4xx (400, 401, 403, 404, 422) -> fail fast immediately
                                self.metrics.total_exhausted_failures += 1
                                logger.error(f"Non-retryable HTTP {status_code} error from OpenRouter: {e.response.text[:300]}")
                                raise e

                        except Exception as e:
                            if attempt < max_retries:
                                delay = self._calculate_backoff_delay(attempt)
                                logger.warning(f"Connection error to OpenRouter (Attempt {attempt}/{max_retries}): {e}. Retrying in {delay:.2f}s...")
                                self.metrics.total_retries += 1
                                await asyncio.sleep(delay)
                                continue
                            else:
                                self.metrics.total_exhausted_failures += 1
                                logger.error(f"OpenRouter connection exhausted retries: {e}")
                                raise e
            finally:
                self._in_flight -= 1

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
