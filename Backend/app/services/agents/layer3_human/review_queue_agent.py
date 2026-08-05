from app.services.graph.state import CostmateState
from app.core.logging import logger

async def build_review_queue_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"[{session_id}] Agent 6: Building Human Review Queue...")
    
    schedule_data = state.get("schedule_registry", {}) or {}
    plan_extractions = state.get("plan_extractions", {}) or {}
    
    queue_items = []
    
    # 1. Schedule Parser consensus failures (Trigger 2)
    for row in schedule_data.get("rows", []):
        if row.get("needs_review"):
            queue_items.append({
                "type": "schedule_mismatch",
                "mark": row.get("mark"),
                "context": row
            })
            
    # 2. OCR consensus failures (Trigger 1)
    for inst in plan_extractions.get("instances", []):
        if inst.get("needs_human_review"):
            queue_items.append({
                "type": "ocr_mismatch",
                "crop_path": inst.get("tag_crop_image_path"),
                "context": inst
            })
            
    # 3. Orphaned marks - dry run join (Trigger 3)
    schedule_marks = [str(r.get("mark", "")).strip().upper() for r in schedule_data.get("rows", [])]
    for inst in plan_extractions.get("instances", []):
        plan_mark = str(inst.get("mark", "")).strip().upper()
        if plan_mark and plan_mark not in schedule_marks and not inst.get("needs_human_review"):
            queue_items.append({
                "type": "orphan_plan_mark",
                "mark": plan_mark,
                "context": inst
            })

    # The interrupt node will pause the graph. We package this into 'qa_prefilled' 
    # to be sent over the SSE stream to the frontend UI.
    prefilled = {
        "review_queue": queue_items,
        "requires_human_intervention": len(queue_items) > 0
    }
    
    return {
        "qa_prefilled": prefilled,
        "current_step": "qa_prefilled",
        "progress_pct": 50
    }
