import asyncio
import json
from rapidfuzz import fuzz
from app.core.openrouter_client import openrouter_client
from app.services.graph.state import CostmateState
from app.core.logging import logger

async def run_ocr_pass(prompt: str, image_paths: list, temperature: float) -> list:
    res = await openrouter_client.generate_chat(prompt=prompt, image_paths=image_paths, json_mode=True, temperature=temperature)
    try:
        data = json.loads(res)
        if isinstance(data, dict) and "marks" in data:
            return data["marks"]
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"OCR Pass Parse Error: {e}")
        return []

async def ocr_consensus_node(state: CostmateState) -> dict:
    logger.info("OCR Consensus: Starting Pass 1 & Pass 2 in parallel...")
    image_paths = state.get("uploaded_page_paths", [])
    if not image_paths:
        return {"ocr_results": {"marks": []}}
        
    prompt1 = "You are a precise OCR engine. Extract ALL door and window marks (e.g. D-1, W-2, RS012) from this floor plan. Output a JSON object with a 'marks' array containing strings."
    prompt2 = "Carefully scan this architectural plan and list every single door or window tag you see. Return ONLY a JSON object with a 'marks' array containing strings."
    
    task1 = run_ocr_pass(prompt1, image_paths, 0.1)
    task2 = run_ocr_pass(prompt2, image_paths, 0.4)
    
    res1, res2 = await asyncio.gather(task1, task2)
    
    # Calculate match
    set1 = set(str(m).strip().upper() for m in res1)
    set2 = set(str(m).strip().upper() for m in res2)
    
    if not set1 and not set2:
        return {"ocr_results": {"marks": []}}
        
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    match_pct = len(intersection) / len(union) if union else 1.0
    
    logger.info(f"OCR Match: {match_pct*100:.2f}%")
    
    if match_pct >= 0.8:
        # High confidence, return intersection
        return {"ocr_results": {"marks": list(intersection), "confidence": match_pct}}
        
    logger.warning("OCR Consensus < 80%. Running Tiebreaker (OCR3)...")
    prompt3 = "Final audit. Extract all door/window marks from this plan. Output JSON object with 'marks' array."
    res3 = await run_ocr_pass(prompt3, image_paths, 0.2)
    set3 = set(str(m).strip().upper() for m in res3)
    
    # 2-of-3 vote
    final_set = set()
    for mark in union.union(set3):
        votes = sum(1 for s in (set1, set2, set3) if mark in s)
        if votes >= 2:
            final_set.add(mark)
            
    return {"ocr_results": {"marks": list(final_set), "confidence": "2-of-3 tiebreaker"}}
