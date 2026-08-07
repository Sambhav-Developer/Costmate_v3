from app.services.graph.state import CostmateState
from app.core.logging import logger

async def reconciliation_node(state: CostmateState) -> dict:
    logger.info("Reconciliation Node: Joining tracks A, B, and C...")
    
    schedule_data = state.get("schedule_data", [])
    ocr_results = state.get("ocr_results", {})
    cv_results = state.get("cv_results", {})
    
    # Extract marks from each track
    schedule_marks = {str(item.get("mark", "")).strip().upper() for item in schedule_data if item.get("mark")}
    
    ocr_marks_list = ocr_results.get("marks", []) if isinstance(ocr_results, dict) else []
    ocr_marks = {str(m).strip().upper() for m in ocr_marks_list}
    
    cv_detections = cv_results.get("detections", [])
    cv_marks = {str(item.get("mark", "")).strip().upper() for item in cv_detections if item.get("mark")}
    
    unresolved_queue = []
    
    # 1. Check for Orphaned Marks (Found in Plan, but NOT in Schedule)
    all_plan_marks = ocr_marks.union(cv_marks)
    
    for plan_mark in all_plan_marks:
        if plan_mark not in schedule_marks:
            unresolved_queue.append({
                "type": "orphan_plan_mark",
                "mark": plan_mark,
                "context": "Found in floor plan but missing from the uploaded schedule."
            })
            
    # 2. Check for Missing Marks (In Schedule, but NOT found in Plan)
    for sched_mark in schedule_marks:
        if sched_mark not in all_plan_marks:
            unresolved_queue.append({
                "type": "missing_from_plan",
                "mark": sched_mark,
                "context": "Exists in schedule but could not be located on the floor plan by OCR or CV."
            })
            
    # 3. Check for CV vs OCR disagreements
    for cv_mark in cv_marks:
        if cv_mark not in ocr_marks:
            unresolved_queue.append({
                "type": "ocr_cv_mismatch",
                "mark": cv_mark,
                "context": "Detected by CV but missed by OCR Consensus."
            })
            
    logger.info(f"Reconciliation complete. Found {len(unresolved_queue)} unresolved items.")
    
    # Map schedule data to V1 qa_prefilled format so the frontend unlocks the Parameters tab
    doors_list = []
    windows_list = []
    
    for item in schedule_data:
        mark = str(item.get("mark", "")).upper()
        # count occurrences on the plan
        count = sum(1 for m in all_plan_marks if str(m).upper() == mark)
        
        obj = {
            "type": mark,
            "count": max(1, count),
            # Pass needs_review through so the UI can show the REVIEW status badge
            "needs_review": bool(item.get("needs_review", False))
        }
        
        ignore_keys = {"mark", "mark_normalized", "mark_norm", "_schedule_type", "type", "count", "needs_review"}
        
        # Known hardware group key name variants (all lowercased for comparison)
        HARDWARE_GROUP_VARIANTS = {
            "hardware group no", "hardware group number", "group no",
            "group number", "hardware group"
        }
        
        # Single pass: iterate original item key order to preserve sequence exactly
        for k, v in item.items():
            kl = str(k).lower()
            if kl in ignore_keys:
                continue
            
            # Normalize hardware group key name variants to the canonical form
            if kl in HARDWARE_GROUP_VARIANTS:
                canonical_key = "HARDWARE GROUP NO"
            else:
                canonical_key = str(k).upper()
            
            if isinstance(v, bool):
                obj[canonical_key] = "True" if v else "False"
            else:
                obj[canonical_key] = v
        
        schedule_type = item.get("_schedule_type", "")
        if schedule_type == "window":
            windows_list.append(obj)
        elif schedule_type == "door":
            doors_list.append(obj)
        else:
            if mark.startswith("W") or mark.startswith("V"):
                windows_list.append(obj)
            else:
                doors_list.append(obj)
            
    qa_prefilled = {
        "project_name": "Auto-Extracted Project",
        "doors": doors_list,
        "windows": windows_list
    }

    # Removed huge JSON terminal log to avoid clutter
    return {
        "current_step": "reconciliation_complete",
        "status": "paused_qa",
        "unresolved_queue": unresolved_queue,
        "qa_prefilled": qa_prefilled
    }
