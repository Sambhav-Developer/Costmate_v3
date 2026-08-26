from app.services.agents.layer1_schedule.schedule_parser import schedule_parser_agent
from app.services.graph.state import CostmateState
from app.core.logging import logger

async def schedule_parser_node(state: CostmateState) -> dict:
    logger.info("Schedule Parser Node: Starting Track A")
    intake_data = state.get("intake_data") or {}
    global_settings = intake_data.get("globalSettings", {})
    
    # Try to extract schedule passed from frontend Step 1
    schedule_data = global_settings.get("scheduleRegistry") or global_settings.get("doorSchedule") or []
    
    # Extract the instance_schedule array if it's a complex dict (V1 prompt structure)
    if isinstance(schedule_data, dict):
        schedule_data = schedule_data.get("instance_schedule") or schedule_data.get("data") or []
        
    if schedule_data and isinstance(schedule_data, list) and len(schedule_data) > 0:
        unique_rows = []
        seen_marks = set()
        for row in schedule_data:
            if not isinstance(row, dict):
                unique_rows.append(row)
                continue
            mark_val = ""
            for k, v in row.items():
                if str(k).lower().strip() in ["mark", "type", "door mark", "door no", "door no.", "id", "mark / type", "mark/type"]:
                    mark_val = str(v).strip().upper()
                    break
            if not mark_val:
                for k, v in row.items():
                    if "mark" in str(k).lower() or "type" in str(k).lower():
                        mark_val = str(v).strip().upper()
                        break
            if mark_val:
                if mark_val in seen_marks:
                    logger.info(f"Schedule Parser Node: Skipping duplicate row for mark {mark_val}")
                    continue
                seen_marks.add(mark_val)
            unique_rows.append(row)
            
        logger.info(f"Schedule Parser Node: Found {len(unique_rows)} unique rows from intake_data (original rows: {len(schedule_data)}).")
        return {"schedule_data": unique_rows}
        
    logger.warning("Schedule Parser Node: No schedule found in intake_data. Falling back to floor plan OCR...")
    
    # Fallback to scanning floor plan for schedule (legacy mode)
    image_paths = state.get("uploaded_page_paths", [])
    if not image_paths:
         return {"schedule_data": []}
    
    # schedule_parser_agent already runs Pass 1 & 2 in parallel via asyncio.gather
    results = await schedule_parser_agent.process_schedule(image_paths)
    
    return {"schedule_data": results}
