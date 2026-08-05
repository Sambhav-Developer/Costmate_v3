import asyncio
from difflib import SequenceMatcher
from typing import Tuple
from app.core.openrouter_client import OpenRouterClient
from app.core.logging import logger

class OCRConsensusAgent:
    def __init__(self):
        self.llm = OpenRouterClient()
        
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculates string similarity ratio (0.0 to 1.0) using normalized edit distance."""
        return SequenceMatcher(None, s1.strip().upper(), s2.strip().upper()).ratio()
        
    async def _run_ocr(self, crop_image_path: str, prompt: str, temperature: float) -> str:
        """Helper to run a single OCR call via Qwen3.5-397B-A17B."""
        res_text = await self.llm.generate_chat(
            prompt=prompt, 
            image_paths=[crop_image_path], 
            json_mode=False, 
            temperature=temperature
        )
        # Strip any accidental whitespace or markdown that might leak through
        return str(res_text).strip().replace("`", "").replace('"', '')

    async def resolve_tag(self, crop_image_path: str) -> Tuple[str, bool]:
        """
        Runs the 3-agent OCR consensus on a tag crop.
        Returns: (resolved_mark: str, needs_human_review: bool)
        """
        # Prompt 1 for Agent 3 (OCR1) - Strict Extraction
        prompt_1 = "You are an expert architectural OCR engine. Read the alphanumeric mark/tag (e.g., D-1, W12, RS012) inside this cropped blueprint image. It represents a door or window schedule tag. Output ONLY the exact characters. Pay strict attention to dashes and architectural fonts."
        
        # Prompt 2 for Agent 4 (OCR2) - Auditor Persona, different temperature
        prompt_2 = "You are a precise vision auditor for civil engineering. Look at the text inside the shape (circle, hexagon, diamond) in this image crop. What is the exact door/window tag number? Beware of visual artifacts or smudges. Respond with the exact tag string only, nothing else."
        
        # Prompt 3 for Agent 5 (OCR3 Tiebreaker) - Different instructions
        prompt_3 = "Final audit. Extract the identifying door/window code shown in this architectural crop. Do not include spaces unless clearly intentional. Distinguish carefully between '0' (zero) and 'O' (letter), and '1' and 'I'. Provide the exact string only."
        
        logger.info(f"OCR Consensus: Starting parallel OCR1 and OCR2 for crop...")
        
        # Task 3.1: Run OCR1 and OCR2 in parallel with distinct configurations
        ocr1_task = asyncio.create_task(self._run_ocr(crop_image_path, prompt_1, temperature=0.1))
        ocr2_task = asyncio.create_task(self._run_ocr(crop_image_path, prompt_2, temperature=0.4))
        
        ocr1_result, ocr2_result = await asyncio.gather(ocr1_task, ocr2_task)
        
        # Task 3.2: 80% match check (normalized edit distance)
        similarity = self._calculate_similarity(ocr1_result, ocr2_result)
        logger.info(f"OCR1: '{ocr1_result}', OCR2: '{ocr2_result}', Similarity: {similarity:.2f}")
        
        if similarity >= 0.80:
            # ≥80% similar → accept as resolved, pass to Excel agent
            # We favor OCR1 (lowest temp) as the canonical spelling if there's a slight mismatch
            resolved = ocr1_result if len(ocr1_result) > 0 else ocr2_result
            return resolved, False
            
        # Task 3.3: If < 80% similar, trigger OCR3 (Tiebreaker)
        logger.warning(f"Similarity < 80% ({similarity:.2f}). Triggering OCR3 Tiebreaker.")
        ocr3_result = await self._run_ocr(crop_image_path, prompt_3, temperature=0.2)
        logger.info(f"OCR3: '{ocr3_result}'")
        
        # Task 3.4: 2-of-3 majority voting
        sim_1_3 = self._calculate_similarity(ocr1_result, ocr3_result)
        sim_2_3 = self._calculate_similarity(ocr2_result, ocr3_result)
        
        if sim_1_3 >= 0.80:
            logger.info("2-of-3 majority reached (OCR1 matches OCR3).")
            return ocr1_result, False
        elif sim_2_3 >= 0.80:
            logger.info("2-of-3 majority reached (OCR2 matches OCR3).")
            return ocr2_result, False
        else:
            # All 3 disagree → send to human review queue; do not guess
            logger.error("All 3 OCR agents disagree. Routing to Human Review Queue.")
            return "", True

ocr_consensus_agent = OCRConsensusAgent()
