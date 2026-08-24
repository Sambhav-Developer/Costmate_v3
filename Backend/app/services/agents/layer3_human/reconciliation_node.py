from app.services.graph.state import CostmateState
from app.core.logging import logger
import re

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
            
    # 4. Cross-check against specifications exclusions (e.g. Aluminium door exclusions)
    specifications_insights = state.get("specifications_insights") or {}
    exclusions = specifications_insights.get("exclusions", [])
    for exclusion in exclusions:
        if any(kw in exclusion.lower() for kw in ["aluminium", "aluminum", "alum"]):
            for item in schedule_data:
                material = ""
                for k, v in item.items():
                    if "material" in str(k).lower():
                        material = str(v).upper()
                        break
                if any(kw in material for kw in ["ALUMINUM", "GLASS", "ALUMINIUM", "ALUM"]):
                    unresolved_queue.append({
                        "type": "aluminium_exclusion_flag",
                        "mark": str(item.get("mark", "")).upper(),
                        "context": f"Specification Exclusion Audit: '{exclusion}'. Verify if this opening should be removed from scope."
                    })

    logger.info(f"Reconciliation complete. Found {len(unresolved_queue)} unresolved items.")
    
    # Map floor plan names from intake and CV detections
    intake = state.get("intake_data") or state.get("intake") or {}
    floors = intake.get("floors", [])
    mark_floors = {}
    for det in cv_detections:
        m = str(det.get("mark", "")).strip().upper()
        fn = det.get("floor_name") or det.get("floor") or det.get("level")
        if m and fn:
            if m not in mark_floors:
                mark_floors[m] = []
            if fn not in mark_floors[m]:
                mark_floors[m].append(fn)

    fallback_floor = ""
    if floors and isinstance(floors, list) and len(floors) > 0:
        fallback_floor = floors[0].get("name") or "Level 1"

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
        
        ignore_keys = {"mark", "mark_normalized", "mark_norm", "_schedule_type", "count", "needs_review", "_schedule_opening_mode"}
        
        # Known hardware group key name variants (all lowercased for comparison)
        HARDWARE_GROUP_VARIANTS = {
            "hardware group no", "hardware group number", "group no",
            "group number", "hardware group", "hw set", "hardware set", "hw_set"
        }
        
        schedule_type = item.get("_schedule_type", "")

        # Single pass: iterate original item key order to preserve sequence exactly
        for k, v in item.items():
            kl = str(k).lower()
            if kl in ignore_keys:
                continue
            
            # Map columns to prevent key collision and ensure duplicate/overlapping headers are visible
            if kl in ["type", "door type", "door_type"]:
                canonical_key = "WINDOW TYPE" if schedule_type == "window" else "DOOR TYPE"
            elif kl in ["frame type", "frame_type"]:
                canonical_key = "FRAME TYPE"
            elif kl in ["material", "door material", "door mat'l", "door_material", "door_mat'l"]:
                canonical_key = "DOOR MATERIAL" if schedule_type == "door" else "WINDOW MATERIAL"
            elif kl in ["frame material", "frame mat'l", "frame_material", "frame_mat'l", "material_1", "material 1"]:
                canonical_key = "FRAME MATERIAL"
            elif kl in ["door finish", "door_finish"]:
                canonical_key = "DOOR FINISH"
            elif kl in ["frame finish", "frame_finish"]:
                canonical_key = "FRAME FINISH"
            elif kl in HARDWARE_GROUP_VARIANTS:
                canonical_key = "HARDWARE GROUP NO"
            elif kl in ["head", "detail head", "detail_head"]:
                canonical_key = "DETAIL HEAD"
            elif kl in ["jamb", "detail jamb", "detail_jamb"]:
                canonical_key = "DETAIL JAMB"
            elif kl in ["sill", "detail sill", "detail_sill"]:
                canonical_key = "DETAIL SILL"
            else:
                canonical_key = str(k).upper()
            
            if isinstance(v, bool):
                obj[canonical_key] = "True" if v else "False"
            else:
                obj[canonical_key] = v
        
        # Check Panel 2 presence in the schedule row
        panel_2_keys = []
        has_hardware = False
        has_material = False
        is_explicit_exterior = False
        
        for k, v in item.items():
            k_lower = str(k).lower().strip()
            v_str = str(v).strip().upper()
            if not v_str or v_str in ["", "-", "N/A", "NONE"]:
                continue
            
            # Panel 2 check
            if "panel 2" in k_lower or "width 2" in k_lower or "panel type 2" in k_lower or k_lower.endswith("_2") or "second" in k_lower or (re.search(r"\b2\b", k_lower) and not re.search(r"\b1\b", k_lower)):
                if v_str not in ["EXIST", "EX", "EXISTING"]:
                    panel_2_keys.append(v_str)
                    
            # Hardware Set check
            if any(hw in k_lower for hw in ["hardware group", "hardware set", "hw set", "group no", "group number"]):
                has_hardware = True
                
            # Material check
            if "material" in k_lower or "mat'l" in k_lower:
                if v_str not in ["EXIST", "EX", "EXISTING"]:
                    has_material = True
                    
        has_panel_2 = len(panel_2_keys) > 0

        # Reconcile Opening Mode and INT/EXT wall type using VLM results from cv_detections
        sched_opening_mode = item.get("_schedule_opening_mode", "SGL")
        mark_dets = [d for d in cv_detections if str(d.get("mark", "")).strip().upper() == mark]
        
        resolved_mode = sched_opening_mode
        if has_panel_2:
            resolved_mode = "PR"
            
        final_opening_mode = resolved_mode
        final_int_ext = "Interior"
        
        if mark_dets:
            det = mark_dets[0]
            vlm_mode = det.get("vlm_opening_mode", "UNKNOWN")
            vlm_wall = det.get("vlm_wall_type", "UNKNOWN")
            
            if vlm_mode != "UNKNOWN":
                # Sanity check cased openings (CO) and revolving (REV)
                is_invalid_co = (vlm_mode == "CO") and (has_hardware or has_material)
                is_invalid_rev = (vlm_mode == "REV") and (has_hardware or has_material)
                
                vlm_mode_cleaned = vlm_mode
                if is_invalid_co or is_invalid_rev:
                    vlm_mode_cleaned = "PR" if has_panel_2 else "SGL"
                    logger.info(f"Reconciliation: Overriding invalid VLM {vlm_mode} for mark {mark} to {vlm_mode_cleaned} (has hardware/material).")
                elif vlm_mode == "PR" and not has_panel_2 and resolved_mode == "SGL":
                    vlm_mode_cleaned = "SGL"
                    logger.info(f"Reconciliation: Overriding VLM PR for mark {mark} to SGL (no Panel 2 in schedule).")

                if resolved_mode == vlm_mode_cleaned:
                    final_opening_mode = resolved_mode
                else:
                    unresolved_queue.append({
                        "type": "opening_mode_conflict",
                        "mark": mark,
                        "context": f"Opening Mode Conflict: Schedule suggests '{resolved_mode}' but floor plan crop reads as '{vlm_mode_cleaned}'. (Reasoning: {det.get('vlm_reasoning', 'VLM detection discrepancy')})"
                    })
                    obj["needs_review"] = True
                    # Prioritize schedule-resolved mode over wrong VLM guess for final output
                    final_opening_mode = resolved_mode
            else:
                final_opening_mode = resolved_mode
            
            final_int_ext = det.get("int_ext", "Interior")
        else:
            final_int_ext = "Unknown"
            
        obj["OPENING MODE"] = final_opening_mode
        obj["INT/EXT"] = final_int_ext
        
        # Shift detail values if they drifted into the FINISH or FRAME FINISH columns
        for finish_key in ["FINISH", "FRAME FINISH"]:
            finish_val = str(obj.get(finish_key, "")).strip()
            if finish_val and re.match(r'^[A-Z0-9]+/[A-Z]\d+', finish_val):
                head_val = obj.get("DETAIL HEAD", "")
                jamb_val = obj.get("DETAIL JAMB", "")
                obj["DETAIL SILL"] = jamb_val
                obj["DETAIL JAMB"] = head_val
                obj["DETAIL HEAD"] = finish_val
                obj[finish_key] = ""
        
        # Ensure Floor / Level column is present using plan upload floor names
        has_floor_col = any(fk.lower() in ["floor", "level", "floor / level", "floor/level", "floor level"] for fk in obj.keys())
        if not has_floor_col:
            if mark in mark_floors and len(mark_floors[mark]) > 0:
                assigned_floor = ", ".join(mark_floors[mark])
            else:
                assigned_floor = fallback_floor
            obj["FLOOR / LEVEL"] = assigned_floor

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
