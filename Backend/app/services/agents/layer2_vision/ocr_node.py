import json
import asyncio
from app.services.graph.state import CostmateState
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.core.prompts import OCR_PROMPT
from app.core.logging import logger

async def ocr_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    image_paths = state.get("uploaded_page_paths", [])
    if not image_paths and state.get("uploaded_file_path"):
        image_paths = [state.get("uploaded_file_path")]
        
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: OCR NODE PIPELINE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 📂 Input Pages: {len(image_paths)} image(s)\n"
                f"  └─ 📁 Paths: {image_paths}")
    
    if not image_paths:
        raise ValueError(f"No image paths provided for OCR node in session {session_id}")

    try:
        intake_data = state.get("intake_data")
        dynamic_prompt = OCR_PROMPT
        if intake_data:
            dynamic_prompt += f"\n\nIMPORTANT CONTEXT FROM USER INTAKE:\n{json.dumps(intake_data, indent=2)}\nPlease use this context to cross-check and validate your OCR output. If the user explicitly declared 3 bedrooms, expect to find 3 bedrooms. This is the absolute source of truth."

        # Run OCR on all pages in parallel
        async def process_page(path, idx):
            logger.info(f"  ├─ 🤖 [Page {idx+1}/{len(image_paths)}] Dispatching vision LLM chat request...")
            response_text = await openrouter_client.generate_chat(
                prompt=dynamic_prompt,
                image_paths=[path],
                json_mode=True
            )
            parsed = parse_json_response(response_text)
            logger.info(f"  ├─ 🎉 [Page {idx+1}/{len(image_paths)}] Vision LLM parsing succeeded. Extracted {len(parsed.get('detected_text_blocks', []))} text blocks.")
            return idx, parsed
            
        results = []
        for idx, path in enumerate(image_paths):
            res = await process_page(path, idx)
            results.append(res)
        
        # Sort by page index to keep order
        results.sort(key=lambda x: x[0])
        
        aggregated_summary = ""
        all_blocks = []
        
        for idx, parsed_data in results:
            summary = parsed_data.get("raw_text_summary", "")
            aggregated_summary += f"\n\n--- PAGE {idx+1} ---\n{summary}"
            
            blocks = parsed_data.get("detected_text_blocks", [])
            for b in blocks:
                b["page_index"] = idx
                all_blocks.append(b)
                
        logger.info(f"----------------------------------------------------------------------\n"
                    f"✅ [{session_id}] COMPLETED: OCR NODE PIPELINE\n"
                    f"  ├─ 🕒 Status: Success\n"
                    f"  ├─ 📊 Total text blocks extracted: {len(all_blocks)}\n"
                    f"  └─ 📝 Aggregated Summary Length: {len(aggregated_summary.strip())} chars\n"
                    f"======================================================================")
        
        return {
            "raw_ocr_text": aggregated_summary.strip(),
            "parsed_image_data": {
                "raw_text_summary": aggregated_summary.strip(),
                "detected_text_blocks": all_blocks
            },
            "current_step": "ocr_completed",
            "progress_pct": 15
        }
    except Exception as e:
        logger.error(f"  ❌ [{session_id}] OCR Node failed with error: {e}")
        logger.info(f"======================================================================")
        raise e

def get_mock_ocr_result() -> dict:
    return {
        "raw_ocr_text": (
            "GROUND FLOOR PLAN. Living Room: 5.0m x 4.0m, Kitchen: 3.0m x 3.0m. "
            "FIRST FLOOR PLAN. Bedroom 1: 4.0m x 4.0m, Bathroom 1: 2.0m x 2.0m. "
            "Column schedule C1: 0.3m x 0.3m. Doors D1: 0.9m x 2.1m. Windows W1: 1.2m x 1.5m."
        ),
        "parsed_image_data": {
            "raw_text_summary": "Extracted room names and dimensions from sample plan",
            "detected_text_blocks": [
                {"text": "GROUND FLOOR PLAN", "location_hint": "center"},
                {"text": "Living Room: 5.0m x 4.0m", "location_hint": "left-center"},
                {"text": "Kitchen: 3.0m x 3.0m", "location_hint": "right-center"},
                {"text": "FIRST FLOOR PLAN", "location_hint": "center"},
                {"text": "Bedroom 1: 4.0m x 4.0m", "location_hint": "left-center"},
                {"text": "Bathroom 1: 2.0m x 2.0m", "location_hint": "right-center"}
            ]
        },
        "current_step": "ocr_completed",
        "progress_pct": 15
    }
