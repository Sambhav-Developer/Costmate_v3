import json
import asyncio
from app.services.graph.state import CostmateState
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.core.prompts import DIMENSION_EXTRACTOR_PROMPT
from app.core.logging import logger
from app.core.floor_utils import normalize_room

async def dimension_extractor_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    image_paths = state.get("uploaded_page_paths", [])
    if not image_paths and state.get("uploaded_file_path"):
        image_paths = [state.get("uploaded_file_path")]
        
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: DIMENSION EXTRACTOR NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 📂 Input Pages: {len(image_paths)} image(s)")
    
    if not image_paths:
        raise ValueError(f"No image paths provided for dimension extractor node in session {session_id}")

    try:
        # Run on all pages in parallel
        async def process_page(path, idx):
            logger.info(f"  ├─ 🤖 [Page {idx+1}/{len(image_paths)}] Extracting room dimensions...")
            response_text = await openrouter_client.generate_chat(
                prompt=DIMENSION_EXTRACTOR_PROMPT,
                image_paths=[path],
                json_mode=True
            )
            parsed = parse_json_response(response_text)
            rooms = parsed.get("rooms", [])
            for r in rooms:
                r["floor_number"] = idx + 1
                normalize_room(r)  # Stilt Floor → Ground Floor
            logger.info(f"  ├─ 🎉 [Page {idx+1}/{len(image_paths)}] Dimensions LLM parsed. Found {len(rooms)} rooms.")
            return parsed
            
        results = []
        for idx, path in enumerate(image_paths):
            res = await process_page(path, idx)
            results.append(res)
        
        # Merge all room
        all_rooms = []
        for dims in results:
            rooms = dims.get("rooms", [])
            for r in rooms:
                all_rooms.append(r)
                
        merged_dimensions = {
            "rooms": all_rooms
        }
        
        logger.info(f"----------------------------------------------------------------------\n"
                    f"✅ [{session_id}] COMPLETED: DIMENSION EXTRACTOR NODE\n"
                    f"  ├─ 🕒 Status: Success\n"
                    f"  ├─ 📊 Total rooms extracted & merged: {len(all_rooms)}\n"
                    f"  └─ 🛌 Rooms List: {[r.get('room_name') for r in all_rooms]}\n"
                    f"======================================================================")
        return {
            "dimensions": merged_dimensions
        }
    except Exception as e:
        logger.error(f"  ❌ [{session_id}] Dimension Extractor Node failed: {e}")
        logger.info(f"======================================================================")
        raise e

def get_mock_dimensions() -> dict:
    return {
        "dimensions": {
            "rooms": [
                {
                    "floor_name": "Ground Floor",
                    "room_name": "Toilet",
                    "length_m": 2.13,
                    "width_m": 1.35,
                    "height_m": 3.0,
                    "source_text": "7' X 4'5\""
                },
                {
                    "floor_name": "Ground Floor",
                    "room_name": "Office",
                    "length_m": 2.82,
                    "width_m": 5.44,
                    "height_m": 3.0,
                    "source_text": "9'3\" X 17'10\""
                },
                {
                    "floor_name": "Ground Floor",
                    "room_name": "Store",
                    "length_m": 1.09,
                    "width_m": 2.69,
                    "height_m": 3.0,
                    "source_text": "3'7\" X 8'10\""
                },
                {
                    "floor_name": "Ground Floor",
                    "room_name": "Lift",
                    "length_m": 1.55,
                    "width_m": 1.25,
                    "height_m": 3.0,
                    "source_text": "1,550 X 1,250"
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Bedroom",
                    "length_m": 3.08,
                    "width_m": 4.675,
                    "height_m": 3.0,
                    "source_text": "3,080 X 4,675 / 10'1\" X 15'4\""
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Toilet",
                    "length_m": 1.7,
                    "width_m": 2.2,
                    "height_m": 3.0,
                    "source_text": "1,700 X 2,200 / 5'7\" X 7'3\""
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Kitchen",
                    "length_m": 3.65,
                    "width_m": 3.65,
                    "height_m": 3.0,
                    "source_text": "3,650 X 3,650 / 12' X 12'"
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Drawing Cum Dining",
                    "length_m": 3.915,
                    "width_m": 7.175,
                    "height_m": 3.0,
                    "source_text": "3,915 X 7,175 / 12'10\" X 23'6\""
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Lift",
                    "length_m": 1.55,
                    "width_m": 1.25,
                    "height_m": 3.0,
                    "source_text": "1,550 X 1,250"
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Wash Balcony",
                    "length_m": 1.5,
                    "width_m": 1.524,
                    "height_m": 3.0,
                    "source_text": "1500MM /5' W"
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Balcony",
                    "length_m": 1.5,
                    "width_m": 1.524,
                    "height_m": 3.0,
                    "source_text": "1500MM /5' W"
                },
                {
                    "floor_name": "First Floor",
                    "room_name": "Puja Room",
                    "length_m": 0.45,
                    "width_m": 0.9,
                    "height_m": 3.0,
                    "source_text": "450 X 900"
                },
                {
                    "floor_name": "Second Floor",
                    "room_name": "DRESSING",
                    "length_m": 3.165,
                    "width_m": 2.16,
                    "height_m": 3.0,
                    "source_text": "3,165 X 2,160 10'5\" X7'1\""
                },
                {
                    "floor_name": "Second Floor",
                    "room_name": "TOILET",
                    "length_m": 3.165,
                    "width_m": 1.5,
                    "height_m": 3.0,
                    "source_text": "3,165 X 1,500 10'5\" X4'11\""
                },
                {
                    "floor_name": "Second Floor",
                    "room_name": "BEDROOM",
                    "length_m": 3.565,
                    "width_m": 3.775,
                    "height_m": 3.0,
                    "source_text": "3,565 X 3,775 11'8\" X12'5\""
                },
                {
                    "floor_name": "Second Floor",
                    "room_name": "ROOM",
                    "length_m": 5.765,
                    "width_m": 3.035,
                    "height_m": 3.0,
                    "source_text": "5,765 X 3,035 18'11\" X9'11\""
                },
                {
                    "floor_name": "Second Floor",
                    "room_name": "LIFT",
                    "length_m": 1.55,
                    "width_m": 1.25,
                    "height_m": 3.0,
                    "source_text": "1,550 X 1,250"
                },
                {
                    "floor_name": "Second Floor",
                    "room_name": "TOILET",
                    "length_m": 2.78,
                    "width_m": 1.35,
                    "height_m": 3.0,
                    "source_text": "2,780 X 1,350 9'1\" X4'5\""
                },
                {
                    "floor_name": "Second Floor",
                    "room_name": "BEDROOM",
                    "length_m": 3.915,
                    "width_m": 3.95,
                    "height_m": 3.0,
                    "source_text": "3,915 X3,950 12'10\" X13'"
                },
                {
                    "floor_name": "Terrace Floor",
                    "room_name": "STORE",
                    "length_m": 3.175,
                    "width_m": 2.311,
                    "height_m": 3.0,
                    "source_text": "10'5\" X7'7\""
                },
                {
                    "floor_name": "Terrace Floor",
                    "room_name": "TOILET",
                    "length_m": 2.819,
                    "width_m": 1.346,
                    "height_m": 3.0,
                    "source_text": "9'3\" X4'5\""
                },
                {
                    "floor_name": "Terrace Floor",
                    "room_name": "LIFT",
                    "length_m": 1.55,
                    "width_m": 1.25,
                    "height_m": 3.0,
                    "source_text": "1,550 X 1,250"
                }
            ]
        }
    }
