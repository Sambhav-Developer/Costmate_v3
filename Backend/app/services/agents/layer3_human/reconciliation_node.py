from app.services.graph.state import CostmateState
from app.core.logging import logger
import re

def parse_door_width_in_inches(w_str: str) -> float:
    w_str = str(w_str).strip().upper()
    if not w_str:
        return 0.0
    if "/" in w_str:
        try:
            parts = [parse_door_width_in_inches(p) for p in w_str.split("/")]
            return sum(parts)
        except:
            pass
    # Feet and inches like 3'-0" or 3-0
    match = re.match(r"^(\d+)'?\s*-\s*(\d+)\"?$", w_str)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        return feet * 12.0 + inches
        
    match_feet = re.match(r"^(\d+)'$", w_str)
    if match_feet:
        return int(match_feet.group(1)) * 12.0
        
    try:
        val = float(w_str.replace('"', '').strip())
        if val <= 10.0:
            return val * 12.0
        return val
    except:
        pass
    return 0.0

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
        has_pair_leaves = False
        door_width_str = ""
        
        for k, v in item.items():
            k_lower = str(k).lower().strip()
            v_str = str(v).strip().upper()
            if not v_str or v_str in ["", "-", "N/A", "NONE"]:
                continue
            
            # Panel 2 check
            if "panel 2" in k_lower or "width 2" in k_lower or "panel type 2" in k_lower or k_lower.endswith("_2") or "second" in k_lower or (re.search(r"\b2\b", k_lower) and not re.search(r"\b1\b", k_lower)):
                if v_str not in ["EXIST", "EX", "EXISTING"]:
                    panel_2_keys.append(v_str)
                    
            # INT/EXT check to recognize exterior doors explicitly declared in the schedule
            if any(ie in k_lower for ie in ["int/ext", "int_ext", "interior/exterior", "int / ext", "interior / exterior"]):
                if any(x in v_str for x in ["EXT", "EXTERNAL", "EXTERIOR"]):
                    is_explicit_exterior = True
                    
            # Leaf count check: e.g. NO. OF LEAVES = 2
            leaves_keys = ["no. of leaves", "leaves", "leaf qty", "panels", "leaves qty", "no. of panels", "leaves number"]
            if any(lk in k_lower for lk in leaves_keys):
                if v_str in ["2", "PR", "DBL", "PAIR", "DOUBLE", "TWO", "2.0"]:
                    has_pair_leaves = True
                    
            # Width check for slash (e.g. 3'-0"/3'-0")
            width_keys = ["width", "size", "dimension", "opening size", "panel size"]
            if any(wk in k_lower for wk in width_keys):
                if "frame" not in k_lower:
                    door_width_str = v_str
                if "/" in v_str:
                    parts = [p.strip() for p in v_str.split("/")]
                    if len(parts) >= 2 and all(re.search(r"\d", p) for p in parts):
                        has_pair_leaves = True
                        
            # Comments/Remarks check for pair indicators
            if any(ck in k_lower for ck in ["comments", "remarks", "estimator notes", "description", "type"]):
                words_in_v = {w.strip(".,()[]{}-_#*") for w in v_str.split()}
                has_pair_keyword = any(kw in v_str for kw in ["PAIR", "2 AUTOMATIC", "2-LEAF", "2-LEAVES", "DOUBLE", "2 LEAF", "2 LEAVES", "TWO LEAF", "TWO LEAVES"])
                if has_pair_keyword or "PR" in words_in_v:
                    has_pair_leaves = True
                    
            # Hardware Set check
            if any(hw in k_lower for hw in ["hardware group", "hardware set", "hw set", "group no", "group number"]):
                has_hardware = True
                
            # Material check
            if "material" in k_lower or "mat'l" in k_lower:
                if v_str not in ["EXIST", "EX", "EXISTING"]:
                    has_material = True
                    
        is_large_width = False
        if door_width_str:
            try:
                width_inches = parse_door_width_in_inches(door_width_str)
                if width_inches >= 50.0:
                    is_large_width = True
            except:
                pass
                
        # Override: if the schedule description or type explicitly specifies SINGLE, it is a single-leaf door
        is_explicit_single = False
        for k, v in item.items():
            k_lower = str(k).lower().strip()
            v_upper = str(v).strip().upper()
            if any(dk in k_lower for dk in ["description", "type", "remarks", "comments", "estimator notes"]):
                if "SINGLE" in v_upper:
                    is_explicit_single = True
                    break

        if is_explicit_single:
            has_panel_2 = False
        else:
            has_panel_2 = len(panel_2_keys) > 0 or has_pair_leaves or is_large_width

        # Reconcile Opening Mode and INT/EXT wall type using VLM results from cv_detections
        sched_opening_mode = item.get("_schedule_opening_mode", "SGL")
        mark_dets = [d for d in cv_detections if str(d.get("mark", "")).strip().upper() == mark]
        
        # Check for Cased Opening (CO) or Double-Acting (DA) in schedule facts
        is_sched_co = False
        is_sched_da = False
        
        door_material = ""
        frame_material = ""
        window_material = ""
        sched_dtype = ""
        sched_comments = ""
        sched_ftype = ""
        for k, v in item.items():
            kl = str(k).lower().strip()
            val_str = str(v).strip().upper()
            
            # 1. Door Material mapping (door panel, panel 1, door material, mat'l, etc.)
            is_dm = False
            if any(x in kl for x in ["door material", "door mat'l", "door matl", "dr mat", "dr mat'l", "dr matl"]):
                is_dm = True
            elif any(x in kl for x in ["panel 1", "door panel", "panel type"]) and "frame" not in kl:
                is_dm = True
            elif ("material" in kl or "mat'l" in kl or "matl" in kl) and "frame" not in kl and "window" not in kl:
                is_dm = True
                
            # 2. Frame Material mapping
            is_fm = False
            if any(x in kl for x in ["frame material", "frame mat'l", "frame matl", "fr mat", "fr mat'l", "fr matl"]):
                is_fm = True
            elif ("material" in kl or "mat'l" in kl or "matl" in kl) and "frame" in kl:
                is_fm = True
                
            # 3. Window Material mapping
            is_wm = ("window" in kl or "glazing" in kl) and ("material" in kl or "mat'l" in kl or "matl" in kl)
            
            if is_dm:
                door_material = val_str
            elif is_fm:
                frame_material = val_str
            elif is_wm:
                window_material = val_str
                
            # 4. Door Type mapping
            is_dt = False
            if any(x in kl for x in ["door type", "dr type", "door design", "door elevation"]):
                is_dt = True
            elif "type" in kl and "frame" not in kl and "window" not in kl:
                is_dt = True
                
            # 5. Frame Type mapping
            is_ft = False
            if any(x in kl for x in ["frame type", "fr type", "frame profile", "frame elevation"]):
                is_ft = True
            elif "type" in kl and "frame" in kl:
                is_ft = True
                
            if is_dt:
                sched_dtype = val_str
            elif is_ft:
                sched_ftype = val_str
            elif any(ck in kl for ck in ["comments", "remarks", "estimator notes", "description"]):
                sched_comments = val_str

        sched_mat = door_material

        # Cased Opening check
        if sched_mat in ["-", "", "NONE", "N/A", "CASED OPENING"] and sched_dtype in ["-", "", "CO", "NONE", "N/A", "CASED OPENING", "CASED"]:
            is_sched_co = True
        elif sched_dtype in ["CO", "CASED OPENING", "CASED"]:
            is_sched_co = True

        # Storefront material check
        is_storefront_opening = False
        
        dm_val = door_material.strip().upper() if door_material else ""
        fm_val = frame_material.strip().upper() if frame_material else ""
        wm_val = window_material.strip().upper() if window_material else ""
        
        def is_sf_mat(m: str) -> bool:
            m_clean = str(m).strip().upper()
            if not m_clean or m_clean in ["-", "N/A", "NA", "NONE", "UNKNOWN"]:
                return True
            # Split by any non-alphanumeric character (e.g. slash, space, hyphen)
            tokens = [t.strip() for t in re.split(r'[^A-Z0-9]', m_clean) if t.strip()]
            sf_tokens = {
                "AL", "ALUM", "ALUMINUM", "ALUMINIUM", "ALLUMINUM", "ALLUMINIUM", "ALM",
                "GL", "GLS", "GLASS", "GLZ", "GLAZING", "GLAZED", "LITE", "LIGHT", "LT",
                "STOREFRONT", "SF", "NA", "N/A"
            }
            return any(t in sf_tokens for t in tokens)
        
        # Check if it is a window schedule mark or explicitly window type
        is_window = (schedule_type == "window") or mark.startswith("W") or mark.startswith("V")
        
        # Check if the mark is explicitly mentioned as storefront in the specifications text
        spec_text = state.get("specifications_text") or ""
        is_spec_storefront = False
        if spec_text and mark:
            # Split specifications text into lines
            lines = [line.strip().upper() for line in re.split(r'[.\n]', spec_text) if line.strip()]
            for line in lines:
                # Split line by spaces and commas, check if the mark is a standalone word
                words_in_line = [w.strip(".,()[]{}-_#*/\"'") for part in line.split() for w in part.split(",")]
                if mark in words_in_line:
                    if any(kw in line for kw in ("STOREFRONT", "EXCLUDE", "EXCLUDED", "ALUMINUM", "ALUM")):
                        is_spec_storefront = True
                        logger.info(f"Reconciliation: Classifying mark {mark} as storefront based on specifications: '{line}'")
                        break
        
        # Check for explicit storefront keywords anywhere in the item data
        all_text = (door_material + " " + frame_material + " " + window_material + " " + sched_dtype + " " + sched_comments + " " + sched_ftype).upper()
        has_storefront_keywords = any(kw in all_text for kw in ("ALUMINUM", "ALUM", "STOREFRONT", "AD SYSTEM"))
        
        has_any_material_spec = bool(dm_val or fm_val or wm_val or sched_ftype)
        if is_spec_storefront:
            is_storefront_opening = True
        elif is_sf_mat(dm_val):
            if is_sf_mat(fm_val) or is_sf_mat(wm_val) or is_sf_mat(sched_ftype):
                # If no material is specified at all in the schedule, only treat as storefront if we have explicit storefront keywords
                if not has_any_material_spec:
                    if has_storefront_keywords:
                        is_storefront_opening = True
                else:
                    # To prevent matching empty dummy cased openings like "3.0 - THIRD":
                    # We require that either it has a width/height, OR has storefront keywords, or it is a window, or has hardware
                    has_dims = bool(item.get("DOOR WIDTH") or item.get("DOOR HEIGHT") or item.get("width") or item.get("height"))
                    if has_dims or has_storefront_keywords or is_window or has_hardware:
                        is_storefront_opening = True
 
        logger.info(f"98C material check: mark={mark}, door={door_material}, frame={frame_material}, window={window_material}, frame_type={sched_ftype} -> is_storefront={is_storefront_opening}")

        # Double-Acting check
        da_phrases = ["DBL ACT", "DBL-ACT", "DOUBLE ACTING", "DOUBLE-ACTING", "DOUBLE ACT", "DOUBLE-ACT", "ANTI-BARRICADE", "ANTI - BARRICADE"]
        da_exact_words = {"DA", "AB"}
        dtype_words = {w.strip(".,()[]{}-_#*") for w in sched_dtype.split()}
        comments_words = {w.strip(".,()[]{}-_#*") for w in sched_comments.split()}
        
        if (any(p in sched_dtype for p in da_phrases) or 
            any(p in sched_comments for p in da_phrases) or 
            da_exact_words.intersection(dtype_words) or 
            da_exact_words.intersection(comments_words)):
            is_sched_da = True

        resolved_mode = sched_opening_mode
        if is_storefront_opening or is_window:
            resolved_mode = "STOREFRONT"
        elif is_sched_co:
            resolved_mode = "CO"
        elif is_sched_da:
            resolved_mode = "DA"
        elif has_panel_2:
            resolved_mode = "PR"
            
        final_opening_mode = resolved_mode
        final_int_ext = "Exterior" if is_explicit_exterior else "Interior"
        
        if mark_dets:
            det = mark_dets[0]
            vlm_mode = det.get("vlm_opening_mode", "UNKNOWN")
            vlm_wall = det.get("vlm_wall_type", "UNKNOWN")
            
            if resolved_mode == "STOREFRONT":
                final_opening_mode = "STOREFRONT"
            elif vlm_mode != "UNKNOWN":
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
                elif resolved_mode == "PR" and vlm_mode_cleaned in ["DE", "DA"]:
                    final_opening_mode = "PR"
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
            
            # Check Curtain Wall frame codes (e.g. FRM-00AL(CW), CW-A03)
            is_curtain_wall = any("(CW)" in str(v).upper() or "CW" in str(v).upper().split("-") or "CW" in str(v).upper().split(".") for v in item.values()) if item else False

            if is_explicit_exterior or is_curtain_wall:
                final_int_ext = "Exterior"
            else:
                geom_int_ext = det.get("int_ext", "Interior")
                vlm_wall = det.get("vlm_wall_type", "UNKNOWN")
                
                final_int_ext = geom_int_ext
                # Conflict Flagging: If geometry indicates Interior but visual crop guessed EXT (e.g. mark 116A)
                if geom_int_ext == "Interior" and vlm_wall in ["EXT", "EXTERIOR"]:
                    logger.info(f"Reconciliation: INT/EXT conflict for mark {mark} (Geometry=Interior, VLM={vlm_wall}). Trusting geometry, flagging review.")
                    unresolved_queue.append({
                        "type": "int_ext_conflict",
                        "mark": mark,
                        "context": f"INT/EXT Conflict: Building perimeter indicates 'Interior', but visual crop scan suggested 'Exterior'. (Flagged for review)."
                    })
                    obj["needs_review"] = True
        else:
            is_curtain_wall = any("(CW)" in str(v).upper() or "CW" in str(v).upper().split("-") or "CW" in str(v).upper().split(".") for v in item.values()) if item else False
            if is_explicit_exterior or is_curtain_wall:
                final_int_ext = "Exterior"
            else:
                final_int_ext = "Unknown"
            
        is_ad_system = "AD SYSTEM" in sched_comments.upper() or "AD SYSTEM" in sched_dtype.upper() or resolved_mode == "STOREFRONT"
        is_window = (schedule_type == "window") or mark.startswith("W") or mark.startswith("V")
        if is_ad_system:
            obj["_is_ad_system"] = True
            obj["_reconciled_opening_mode"] = "STOREFRONT"
            obj["_reconciled_int_ext"] = ""
        else:
            if not is_window:
                obj["_reconciled_opening_mode"] = final_opening_mode
            obj["_reconciled_int_ext"] = final_int_ext
        
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
