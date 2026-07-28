import json
import asyncio
from app.services.graph.state import CostmateState
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.core.prompts import FLOOR_PLAN_READER_PROMPT
from app.core.logging import logger
from app.core.floor_utils import normalize_floor

async def floor_plan_reader_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    image_paths = state.get("uploaded_page_paths", [])
    if not image_paths and state.get("uploaded_file_path"):
        image_paths = [state.get("uploaded_file_path")]
        
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: FLOOR PLAN READER NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 📂 Input Pages: {len(image_paths)} image(s)")
    
    if not image_paths:
        raise ValueError(f"No image paths provided for floor plan reader node in session {session_id}")

    try:
        # Run on all pages in parallel
        async def process_page(path, idx):
            logger.info(f"  ├─ 🤖 [Page {idx+1}/{len(image_paths)}] Extracting floor plan structures...")
            response_text = await openrouter_client.generate_chat(
                prompt=FLOOR_PLAN_READER_PROMPT,
                image_paths=[path],
                json_mode=True
            )
            parsed = parse_json_response(response_text)
            floors = parsed.get("floors", [])
            for fl in floors:
                fl["floor_number"] = idx + 1
                normalize_floor(fl)  # Stilt Floor → Ground Floor
            logger.info(f"  ├─ 🎉 [Page {idx+1}/{len(image_paths)}] Floor Plan Reader LLM parsed. Found floors: {[f.get('floor_name') for f in floors]}")
            return parsed
            
        results = []
        for idx, path in enumerate(image_paths):
            res = await process_page(path, idx)
            results.append(res)
        
        # Merge floor plan results
        all_floors = []
        seen_floor_names = set()
        
        for plan in results:
            floors = plan.get("floors", [])
            for fl in floors:
                # Basic deduping by name
                name = fl.get("floor_name", "").strip().lower()
                if name and name not in seen_floor_names:
                    seen_floor_names.add(name)
                    all_floors.append(fl)
                elif not name:
                    all_floors.append(fl)
                    
        # Sort floors by floor_number
        all_floors.sort(key=lambda x: x.get("floor_number", 1))
        
        # Re-index floor numbers to be contiguous
        for idx, fl in enumerate(all_floors):
            fl["floor_number"] = idx + 1
            
        merged_plan = {
            "num_floors": len(all_floors),
            "floors": all_floors
        }
        
        logger.info(f"----------------------------------------------------------------------\n"
                    f"✅ [{session_id}] COMPLETED: FLOOR PLAN READER NODE\n"
                    f"  ├─ 🕒 Status: Success\n"
                    f"  ├─ 📊 Total floors parsed & merged: {len(all_floors)}\n"
                    f"  └─ 🏠 Floor Names: {[f.get('floor_name') for f in all_floors]}\n"
                    f"======================================================================")
        return {
            "floor_plan": merged_plan
        }
    except Exception as e:
        logger.error(f"  ❌ [{session_id}] Floor Plan Reader Node failed: {e}")
        logger.info(f"======================================================================")
        raise e

def get_mock_floor_plan() -> dict:
    return {
        "floor_plan": {
            "num_floors": 4,
            "floors": [
                {
                    "floor_number": 1,
                    "floor_name": "Ground Floor",
                    "rooms": ["Toilet", "Office", "Store", "Lift", "Staircase"],
                    "footprint_length_m": 9.1,
                    "footprint_width_m": 15.2
                },
                {
                    "floor_number": 2,
                    "floor_name": "First Floor",
                    "rooms": ["Bedroom", "Toilet", "Kitchen", "Drawing Cum Dining", "Lift", "Balcony", "Wash Balcony", "Pooja Room"],
                    "footprint_length_m": 7.245,
                    "footprint_width_m": 12.84
                },
                {
                    "floor_number": 3,
                    "floor_name": "Terrace Floor",
                    "rooms": ["Store", "Toilet", "Lift", "Terrace"],
                    "footprint_length_m": 7.245,
                    "footprint_width_m": 9.84
                },
                {
                    "floor_number": 4,
                    "floor_name": "Second Floor",
                    "rooms": ["Dressing 1", "Toilet 1", "Bedroom 1", "Room", "Lift", "Dressing 2", "Toilet 2", "Bedroom 2", "Balcony"],
                    "footprint_length_m": 7.245,
                    "footprint_width_m": 9.84
                }
            ]
        }
    }
