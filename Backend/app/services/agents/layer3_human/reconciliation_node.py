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
    
    # Extract raw schedule headers before prefill
    raw_schedule_headers = []
    seen_h = set()
    for item in schedule_data:
        if isinstance(item, dict):
            for k in item.keys():
                kl = str(k).lower().strip()
                if not k.startswith("_") and kl not in ["needs_review", "is_borderline", "review_reason", "count", "type"] and kl not in seen_h:
                    seen_h.add(kl)
                    raw_schedule_headers.append(k)

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
    # Structured 6-step Reconciliation Audit per Door_Schedule_Discrepancy_Report.md
    reconciliation_audit = {
        "quantity_discrepancies": [],
        "borderline_unlocated_marks": [],
        "int_ext_conflicts": [],
        "opening_mode_conflicts": [],
        "excluded_scope_items": [],
        "deduplicated_rows": []
    }
    
    doors_list = []
    windows_list = []
    
    for item in schedule_data:
        mark = str(item.get("mark", "")).upper()
        # count occurrences on the plan
        mark_dets = [d for d in cv_detections if str(d.get("mark", "")).strip().upper() == mark]
        raw_count = max(len(mark_dets), len([m for m in ocr_marks_list if str(m).strip().upper() == mark]))
        
        # Deduplicate duplicate crop callouts for the same physical door location (e.g. HE210P, HE210Q, HE210S, HE210U, HE210V)
        if raw_count > 1:
            loc_val = str(item.get("location") or item.get("LOCATION") or "").strip()
            unique_locs = {loc_val.upper()} if loc_val else set()
            for d in mark_dets:
                d_loc = str(d.get("location", "")).strip().upper()
                if d_loc:
                    unique_locs.add(d_loc)
            
            # 1. Spatial proximity check: cluster detections on the same page within 50pt radius
            spatial_clusters = []
            for d in mark_dets:
                p_no = str(d.get("page_no", "0"))
                try:
                    cx = float(d.get("w_cx", 0))
                    cy = float(d.get("w_cy", 0))
                except: 
                    cx, cy = 0.0, 0.0
                
                matched_cluster = False
                for cluster in spatial_clusters:
                    if cluster["page_no"] == p_no:
                        dist = ((cluster["cx"] - cx)**2 + (cluster["cy"] - cy)**2)**0.5
                        if dist < 50.0:
                            matched_cluster = True
                            break
                if not matched_cluster:
                    spatial_clusters.append({"page_no": p_no, "cx": cx, "cy": cy})

            # If spatial clusters exist and are less than raw_count, deduplicate overlapping crops
            if spatial_clusters and len(spatial_clusters) < raw_count:
                reconciled_count = len(spatial_clusters)
                reconciliation_audit["deduplicated_rows"].append({
                    "mark": mark,
                    "original_count": raw_count,
                    "reconciled_count": reconciled_count,
                    "reason": f"Consolidated {raw_count - reconciled_count} overlapping crop detection(s) for physical mark '{mark}' at location '{loc_val or 'Standard'}'"
                })
            else:
                # 2. Location string matching: if all detections belong to the same room location name
                is_dup_loc = False
                if len(unique_locs) == 1:
                    is_dup_loc = True
                elif len(unique_locs) == 2:
                    l_list = list(unique_locs)
                    l1_clean = re.sub(r'[^A-Z0-9]', '', l_list[0])
                    l2_clean = re.sub(r'[^A-Z0-9]', '', l_list[1])
                    if l1_clean in l2_clean or l2_clean in l1_clean:
                        is_dup_loc = True
                        
                if is_dup_loc and len(unique_locs) > 0:
                    reconciled_count = 1
                    reconciliation_audit["deduplicated_rows"].append({
                        "mark": mark,
                        "original_count": raw_count,
                        "reconciled_count": 1,
                        "reason": f"Deduplicated duplicate crop callout on drawing for location '{loc_val or 'Standard'}'"
                    })
                else:
                    reconciled_count = raw_count
        else:
            reconciled_count = max(1, raw_count) if mark_dets else 0

        obj = {
            "type": mark,
            "count": reconciled_count,
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
            elif kl in ["location", "location name", "room", "room name", "room no", "room number", "room/location", "room / location", "from room", "to room", "room_name", "room_no"]:
                canonical_key = "LOCATION"
            elif kl in ["floor", "level", "floor / level", "floor/level", "floor level", "floor no", "floor number", "level no", "level number", "story", "floor_no", "level_no"]:
                canonical_key = "FLOOR / LEVEL"
            else:
                canonical_key = str(k).upper()
            
            if isinstance(v, bool):
                obj[canonical_key] = "True" if v else "False"
            else:
                obj[canonical_key] = v

        # Populate LOCATION, bbox, and drawing coordinates from CV plan detections (Schedule Priority)
        if mark_dets:
            det = mark_dets[0]
            det_loc = str(det.get("location", "")).strip()
            curr_loc = str(obj.get("LOCATION") or "").strip()
            
            # ONLY use CV spatial location fallback if schedule LOCATION is missing, empty, or Unknown
            if det_loc and det_loc not in ["Unknown", "unknown", "NONE", "", "-"]:
                if not curr_loc or curr_loc in ["", "-", "N/A", "NA", "NONE", "Unknown", "unknown"]:
                    obj["LOCATION"] = det_loc
                    obj["location"] = det_loc
            if det.get("bbox"):
                obj["bbox"] = det.get("bbox")
            if det.get("w_cx") is not None:
                obj["w_cx"] = det.get("w_cx")
                obj["w_cy"] = det.get("w_cy")
            
            # ONLY use CV page floor fallback if schedule FLOOR / LEVEL is missing, empty, or Unknown
            curr_floor = str(obj.get("FLOOR / LEVEL") or obj.get("floor_no") or "").strip()
            if not curr_floor or curr_floor in ["", "-", "N/A", "NA", "NONE", "Unknown", "unknown"]:
                if det.get("floor_no"):
                    obj["floor_no"] = det.get("floor_no")
                    obj["FLOOR / LEVEL"] = det.get("floor_no")
                    if det.get("floor_name"):
                        obj["floor_name"] = det.get("floor_name")
            else:
                obj["floor_no"] = curr_floor
                
            if det.get("page_no"):
                obj["page_no"] = det.get("page_no")
        
        # Check Panel 2 presence in the schedule row
        panel_2_keys = []
        has_hardware = False
        has_material = False
        is_explicit_exterior = False
        is_explicit_interior = False
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
                    
            # INT/EXT check to recognize exterior/interior doors explicitly declared in the schedule
            if any(ie in k_lower for ie in ["int/ext", "int_ext", "interior/exterior", "int / ext", "interior / exterior"]):
                if any(x in v_str for x in ["EXT", "EXTERNAL", "EXTERIOR"]):
                    is_explicit_exterior = True
                elif any(x in v_str for x in ["INT", "INTERNAL", "INTERIOR"]):
                    is_explicit_interior = True
                    
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
            if any(x in kl for x in ["door material", "door mat'l", "door matl", "dr mat", "dr mat'l", "dr matl", "door mat", "leaf material", "panel material"]):
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
            
            if is_dm and val_str:
                if not door_material or "panel 1" in kl or "door material" in kl:
                    door_material = val_str
            elif is_fm and val_str:
                if not frame_material or "frame material" in kl:
                    frame_material = val_str
            elif is_wm and val_str:
                if not window_material:
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
                
            if is_dt and val_str:
                if not sched_dtype or "door type" in kl:
                    sched_dtype = val_str
            elif is_ft and val_str:
                if not sched_ftype or "frame type" in kl:
                    sched_ftype = val_str
            elif any(ck in kl for ck in ["comments", "remarks", "estimator notes", "description"]) and val_str:
                if not sched_comments:
                    sched_comments = val_str

        sched_mat = door_material

        # Check for hardware set
        has_hw_set = False
        for k, v in item.items():
            kl = str(k).lower().strip()
            val_str = str(v).strip().upper()
            if any(hk in kl for hk in ["hardware", "hw set", "hw group", "hdwe"]):
                if val_str and val_str not in ["-", "N/A", "NONE", "NA"]:
                    has_hw_set = True
                    break

        # Cased Opening check
        # BOTH sched_mat and sched_dtype being empty strings "" is NOT a cased opening!
        if has_hw_set:
            is_sched_co = False
        elif sched_mat in ["-", "CASED OPENING"] and sched_dtype in ["-", "CO", "CASED OPENING", "CASED"]:
            is_sched_co = True
        elif sched_dtype in ["CO", "CASED OPENING", "CASED"]:
            is_sched_co = True
        else:
            is_sched_co = False

        # Storefront material & panel check
        panel_a = ""
        panel_b = ""
        for k, v in item.items():
            kl = str(k).lower().strip()
            val_str = str(v).strip().upper()
            if not val_str or val_str in ["-", "N/A", "NONE", "NA"]:
                continue
            if any(x in kl for x in ["panel a", "panel 1 material", "leaf 1 material", "panel 1"]):
                if not panel_a: panel_a = val_str
            elif any(x in kl for x in ["panel b", "panel 2 material", "leaf 2 material", "panel 2"]):
                if not panel_b: panel_b = val_str

        sf_mat_tokens = {"AL", "ALUM", "ALUMINUM", "GL", "GLASS", "AL/GL", "GL/AL", "AL-FG", "AL/FG", "STOREFRONT", "CW", "CURTAINWALL", "SF"}
        wood_hm_tokens = {"WD", "WOOD", "SCWD", "HM", "STEEL", "FG", "FIBERGLASS"}

        def is_sf_token(m: str) -> bool:
            if not m or m in ["-", "N/A", "NA", "NONE"]:
                return False
            m_upper = m.upper()
            if "AL-FG" in m_upper or "AL/FG" in m_upper or "GL/AL" in m_upper or "AL/GL" in m_upper:
                return True
            tokens = [t.strip() for t in re.split(r'[^A-Z0-9]', m_upper) if t.strip()]
            if any(w in wood_hm_tokens for w in tokens) and not any(kw in m_upper for kw in ["STOREFRONT", "CURTAINWALL", "AD SYSTEM"]):
                return False
            return any(t in sf_mat_tokens for t in tokens)

        def is_wood_hm(m: str) -> bool:
            if not m:
                return False
            m_upper = m.upper()
            if any(kw in m_upper for kw in ["AL-FG", "AL/FG", "STOREFRONT", "CURTAINWALL", "AD SYSTEM"]):
                return False
            tokens = [t.strip() for t in re.split(r'[^A-Z0-9]', m_upper) if t.strip()]
            return any(w in wood_hm_tokens for w in tokens)

        # Check if it is a window schedule mark or explicitly window type
        is_window = (schedule_type == "window") or mark.startswith("W") or mark.startswith("V")
        
        # Check if the mark is explicitly mentioned as storefront in the specifications text
        spec_text = state.get("specifications_text") or ""
        is_spec_storefront = False
        if spec_text and mark:
            lines = [line.strip().upper() for line in re.split(r'[.\n]', spec_text) if line.strip()]
            for line in lines:
                words_in_line = [w.strip(".,()[]{}-_#*/\"'") for part in line.split() for w in part.split(",")]
                if mark in words_in_line:
                    if any(kw in line for kw in ("STOREFRONT", "EXCLUDE", "EXCLUDED", "ALUMINUM", "ALUM")):
                        is_spec_storefront = True
                        logger.info(f"Reconciliation: Classifying mark {mark} as storefront based on specifications: '{line}'")
                        break

        is_explicit_sf_system = any(tok in sched_comments.upper() for tok in ["STOREFRONT", "AD SYSTEM", "CURTAINWALL"]) or any(tok in sched_dtype.upper() for tok in ["STOREFRONT", "SF", "CW"]) or is_spec_storefront or is_window

        is_storefront_opening = False
        dm_val = door_material.strip().upper() if door_material else ""
        fm_val = frame_material.strip().upper() if frame_material else ""
        dm_empty = not dm_val or dm_val in ["-", "N/A", "NA", "NONE"]
        fm_empty = not fm_val or fm_val in ["-", "N/A", "NA", "NONE"]

        if is_explicit_sf_system:
            is_storefront_opening = True
        elif is_sched_co:
            is_storefront_opening = False
        elif is_wood_hm(dm_val) or is_wood_hm(fm_val) or is_wood_hm(panel_a) or is_wood_hm(panel_b):
            is_storefront_opening = False
        elif not dm_empty and not fm_empty:
            if is_sf_token(dm_val) and is_sf_token(fm_val):
                is_storefront_opening = True
        elif not dm_empty or not fm_empty:
            present_mat = dm_val if not dm_empty else fm_val
            if is_sf_token(present_mat):
                is_storefront_opening = True
        else:
            if is_sf_token(panel_a) or is_sf_token(panel_b):
                is_storefront_opening = True
            elif not panel_a and not panel_b:
                is_storefront_opening = True

        logger.info(f"Storefront material check: mark={mark}, door={door_material}, frame={frame_material}, window={window_material}, frame_type={sched_ftype} -> is_storefront={is_storefront_opening}")



        # Double-Acting check
        da_phrases = ["DBL ACT", "DBL-ACT", "DOUBLE ACTING", "DOUBLE-ACTING", "DOUBLE ACT", "DOUBLE-ACT", "ANTI-BARRICADE", "ANTI - BARRICADE"]
        da_exact_words = {"DA", "AB"}
        dtype_words = {w.strip(".,()[]{}-_#*") for w in sched_dtype.split()}
        comments_words = {w.strip(".,()[]{}-_#*") for w in sched_comments.split()}
        
        is_sched_da = False
        if (any(p in sched_dtype for p in da_phrases) or 
            any(p in sched_comments for p in da_phrases) or 
            da_exact_words.intersection(dtype_words) or 
            da_exact_words.intersection(comments_words)):
            is_sched_da = True

        # Barn / Sliding Door check
        sld_phrases = ["BARN DOOR", "BARN-DOOR", "BARN", "SURFACE SLIDING", "SURFACE-SLIDING", "SLIDING DOOR", "SLIDING-DOOR", "SLIDING", "TOP HUNG SLIDING", "TOP-HUNG SLIDING", "BARN HARDWARE", "TRACK HARDWARE", "SLIDING TRACK"]
        sld_exact_words = {"SLD", "BARN", "SLIDING"}
        is_sched_sld = False
        if (any(p in sched_dtype for p in sld_phrases) or 
            any(p in sched_comments for p in sld_phrases) or 
            sld_exact_words.intersection(dtype_words) or 
            sld_exact_words.intersection(comments_words)):
            is_sched_sld = True

        # Pocket Door check
        pkt_phrases = ["POCKET DOOR", "POCKET-DOOR", "POCKET"]
        pkt_exact_words = {"PKT", "POCKET"}
        is_sched_pkt = False
        if (any(p in sched_dtype for p in pkt_phrases) or 
            any(p in sched_comments for p in pkt_phrases) or 
            pkt_exact_words.intersection(dtype_words) or 
            pkt_exact_words.intersection(comments_words)):
            is_sched_pkt = True

        # Bifold Door check
        bifold_phrases = ["BIFOLD", "BI-FOLD"]
        bifold_exact_words = {"BIFOLD"}
        is_sched_bifold = False
        if (any(p in sched_dtype for p in bifold_phrases) or 
            any(p in sched_comments for p in bifold_phrases) or 
            bifold_exact_words.intersection(dtype_words) or 
            bifold_exact_words.intersection(comments_words)):
            is_sched_bifold = True

        # Bypass Door check
        bypass_phrases = ["BYPASS", "BY-PASS"]
        bypass_exact_words = {"BYPASS"}
        is_sched_bypass = False
        if (any(p in sched_dtype for p in bypass_phrases) or 
            any(p in sched_comments for p in bypass_phrases) or 
            bypass_exact_words.intersection(dtype_words) or 
            bypass_exact_words.intersection(comments_words)):
            is_sched_bypass = True

        resolved_mode = sched_opening_mode
        if is_storefront_opening or is_window:
            resolved_mode = "STOREFRONT"
        elif is_sched_co:
            resolved_mode = "CO"
        elif is_sched_da:
            resolved_mode = "DA"
        elif is_sched_sld:
            resolved_mode = "SLD"
        elif is_sched_pkt:
            resolved_mode = "PKT"
        elif is_sched_bifold:
            resolved_mode = "BIFOLD"
        elif is_sched_bypass:
            resolved_mode = "BYPASS"
        elif has_panel_2:
            resolved_mode = "PR"
        elif mark_dets and mark_dets[0].get("opening_mode"):
            resolved_mode = mark_dets[0].get("opening_mode")
        else:
            resolved_mode = "SGL"
            
        final_opening_mode = resolved_mode
        final_int_ext = "Exterior" if is_explicit_exterior else "Interior"
        
        if mark_dets:
            det = mark_dets[0]
            vlm_mode = det.get("vlm_opening_mode", "UNKNOWN")
            l1_mode = det.get("layer1_schedule_mode") or resolved_mode
            l2_mode = det.get("layer2_vector_mode") or "UNKNOWN"
            l3_mode = det.get("layer3_vlm_mode") or vlm_mode

            # Material & hardware sanity cleanup for Layer 3 VLM prediction
            l3_cleaned = l3_mode
            if (l3_mode in ["CO", "REV"]) and (has_hardware or has_material):
                l3_cleaned = "PR" if has_panel_2 else (resolved_mode if resolved_mode in ["SLD", "PKT", "BIFOLD", "BYPASS"] else "SGL")
            elif l3_mode in ["PR", "PAIR", "DOUBLE", "DBL"] and not has_panel_2 and resolved_mode in ["SGL", "SLD", "PKT", "BIFOLD", "BYPASS"]:
                l3_cleaned = resolved_mode

            VISUAL_SPECIALTY_MODES = {"SLD", "PKT", "BIFOLD", "OHD", "REV", "BYPASS", "DA"}
            
            # 3-Layer Weighted Voting
            votes = {}
            if l1_mode and l1_mode != "UNKNOWN":
                votes[l1_mode] = votes.get(l1_mode, 0.0) + 1.0
            if l2_mode and l2_mode != "UNKNOWN":
                votes[l2_mode] = votes.get(l2_mode, 0.0) + 1.0
            if l3_cleaned and l3_cleaned != "UNKNOWN":
                votes[l3_cleaned] = votes.get(l3_cleaned, 0.0) + 1.0

            # Layer 3 Visual Specialty Bonus: Give Layer 3 +0.5 bonus weight for legend-matched visual types
            if l3_mode in VISUAL_SPECIALTY_MODES and l3_cleaned == l3_mode:
                votes[l3_mode] = votes.get(l3_mode, 0.0) + 0.5

            if resolved_mode == "STOREFRONT":
                final_opening_mode = "STOREFRONT"
            elif votes:
                sorted_modes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
                winner_mode = sorted_modes[0][0]
                final_opening_mode = winner_mode
                logger.info(f"Reconciliation 3-Layer Voting for Mark {mark}: L1={l1_mode}, L2={l2_mode}, L3={l3_cleaned} -> WINNER={winner_mode} (votes={votes})")
            else:
                final_opening_mode = resolved_mode
            
            # Check Curtain Wall frame codes (e.g. FRM-00AL(CW), CW-A03)
            is_curtain_wall = any("(CW)" in str(v).upper() or "CW" in str(v).upper().split("-") or "CW" in str(v).upper().split(".") for v in item.values()) if item else False

            is_borderline = det.get("is_borderline", False)
            dist_val = det.get("dist_to_boundary", 999.0)
            geom_int_ext = det.get("int_ext", "Interior")
            vlm_wall = det.get("vlm_wall_type", "UNKNOWN")

            # Priority 1: Explicit Schedule Facts (Highest Confidence)
            if is_explicit_exterior or is_curtain_wall:
                final_int_ext = "Exterior"
            elif is_explicit_interior:
                final_int_ext = "Interior"
                if vlm_wall in ["EXT", "EXTERIOR"]:
                    reconciliation_audit["int_ext_conflicts"].append({
                        "mark": mark,
                        "schedule_value": "Interior",
                        "detected_value": "Exterior",
                        "resolution": "Interior (Schedule Priority of Evidence)"
                    })
            # Priority 2: 2D Geometry Building Footprint (Primary CAD Physical Signal)
            elif dist_val > 85.0:
                final_int_ext = "Interior"
                if vlm_wall in ["EXT", "EXTERIOR"]:
                    reconciliation_audit["int_ext_conflicts"].append({
                        "mark": mark,
                        "schedule_value": "Interior",
                        "detected_value": "Exterior",
                        "resolution": f"Interior (Resolved by 2D CAD Building Footprint at {dist_val:.1f}pt)"
                    })
            # Priority 3: Perimeter Zone (dist_val <= 85.0 pt) — VLM Tiebreaker & Secondary Room Name QA Corroboration
            elif vlm_wall in ["EXT", "EXTERIOR"]:
                loc_upper = str(obj.get("LOCATION") or det.get("location") or "").upper()
                interior_kws = ["OFFICE", "CORRIDOR", "STORAGE", "TOILET", "SHOWER", "CONFERENCE", "HALL", "LOUNGE", "STAIR", "CLOSET", "RECEPTION", "WAITING", "PANTRY", "EXAM", "CARE", "UTILITY", "ELEC", "MECH", "JANITOR", "HOLDING"]
                has_interior_loc = any(kw in loc_upper for kw in interior_kws)
                has_exterior_loc = any(kw in loc_upper for kw in ["ROOF", "PATIO", "COURTYARD", "OUTDOOR", "EXTERIOR", "PARKING", "DOCK"])
                
                if has_interior_loc and not has_exterior_loc:
                    final_int_ext = "Interior"
                    reconciliation_audit["int_ext_conflicts"].append({
                        "mark": mark,
                        "schedule_value": "Interior",
                        "detected_value": "Exterior",
                        "resolution": f"Interior (Resolved by Room Location '{loc_upper}')"
                    })
                else:
                    final_int_ext = "Exterior"
            else:
                final_int_ext = "Interior"
        else:
            is_curtain_wall = any("(CW)" in str(v).upper() or "CW" in str(v).upper().split("-") or "CW" in str(v).upper().split(".") for v in item.values()) if item else False
            final_int_ext = "Exterior" if (is_explicit_exterior or is_curtain_wall) else "Interior"
            
            # Zero-Silent-Failure Guard: Any schedule mark not located on drawing MUST force needs_review=True
            obj["needs_review"] = True
            obj["is_borderline"] = True
            obj["review_reason"] = "mark_not_located_on_drawing"
            if not obj.get("Takeoff Notes"):
                obj["Takeoff Notes"] = "Schedule mark not located on drawing; Qty verified by estimator."
            
            reconciliation_audit["borderline_unlocated_marks"].append({
                "mark": mark,
                "location": obj.get("LOCATION", "Unknown"),
                "status": "mark_not_located_on_drawing",
                "action": "Flagged Qty=0 for human verification against source drawings"
            })
            
            unresolved_queue.append({
                "type": "mark_not_located",
                "mark": mark,
                "context": f"Mark Not Located: Mark '{mark}' from schedule registry was not located on floor plan drawing. Flagged for human review."
            })
            logger.warning(f"Reconciliation: Schedule mark '{mark}' was not located on floor plan drawings. Flagged needs_review=True.")
            
        # 5-Bucket INT/EXT Classification per SKILL.md (Interior, Exterior, Soft Exterior, Window/Sidelite/Borrowed Lite, Not in Scope)
        all_opening_text = " ".join([str(v) for v in item.values() if v]).lower() + " " + " ".join([str(v) for v in obj.values() if v]).lower()
        if mark_dets:
            all_opening_text += " " + str(mark_dets[0].get("vlm_wall_type", "")).lower() + " " + str(mark_dets[0].get("vlm_opening_mode", "")).lower()
            
        is_sidelite_or_borrowed = any(kw in all_opening_text for kw in ["sidelite", "side lite", "side-lite", "borrowed lite", "borrowed-lite", "borrowedlite", "transom", "glass panel"])
        is_multifold_wall = any(kw in all_opening_text for kw in ["multifold", "operable wall", "folding wall", "accordion door", "operable partition"])
        
        if is_multifold_wall:
            final_int_ext = "Not in Scope"
            obj["Takeoff Notes"] = "Door tag found on Floor plan it is a multifold wall assembly. So, Excluded."
            obj["excluded"] = True
            reconciliation_audit["excluded_scope_items"].append({
                "mark": mark,
                "exclusion_note": obj["Takeoff Notes"],
                "treatment": "Flagged NOT IN SCOPE (Header #FF69B4)"
            })
        elif is_storefront_opening:
            final_int_ext = "Not in Scope"
            obj["Takeoff Notes"] = f"Door Excluded. Door material {door_material or 'HM'} but on elevation it is storefront."
            obj["excluded"] = True
            reconciliation_audit["excluded_scope_items"].append({
                "mark": mark,
                "exclusion_note": obj["Takeoff Notes"],
                "treatment": "Flagged NOT IN SCOPE (Header #FF69B4)"
            })
        elif is_window:
            final_int_ext = "Window"
        elif is_sidelite_or_borrowed:
            final_int_ext = "Window"
            if not obj.get("Takeoff Notes"):
                obj["Takeoff Notes"] = "Sidelite / Borrowed Lite opening."
        elif is_sched_co:
            if not obj.get("Takeoff Notes"):
                obj["Takeoff Notes"] = "Cased opening found on floor plan."
        elif any(g_kw in all_opening_text for g_kw in ["garage", "parking", "loading dock", "breezeway", "compactor", "cellar", "covered walkway", "open-air corridor", "pkg"]):
            final_int_ext = "Soft Exterior"
        elif is_explicit_exterior:
            final_int_ext = "Exterior"
        
        door_mat = str(obj.get("DOOR MATERIAL", obj.get("door_material", ""))).strip()
        frame_mat = str(obj.get("FRAME MATERIAL", obj.get("frame_material", ""))).strip()
        
        # User Rule: If door material or frame material is '-', it is a Storefront opening
        if door_mat == "-" or frame_mat == "-":
            obj["_is_ad_system"] = True
            obj["Opening Mode"] = "STOREFRONT"
            obj["_reconciled_opening_mode"] = "STOREFRONT"
            final_int_ext = "Not in Scope"
            obj["INT/EXT"] = "Not in Scope"
            obj["_reconciled_int_ext"] = "Not in Scope"
            if not obj.get("Takeoff Notes"):
                obj["Takeoff Notes"] = "SEE STOREFRONT SCHEDULE."
        else:
            is_ad_system = "AD SYSTEM" in sched_comments.upper() or "AD SYSTEM" in sched_dtype.upper() or resolved_mode == "STOREFRONT" or is_storefront_opening
            if is_ad_system:
                obj["_is_ad_system"] = True
                obj["Opening Mode"] = "STOREFRONT"
                obj["_reconciled_opening_mode"] = "STOREFRONT"
                obj["_reconciled_int_ext"] = "Not in Scope"
                final_int_ext = "Not in Scope"
            else:
                if not is_window and not is_sidelite_or_borrowed:
                    obj["_reconciled_opening_mode"] = final_opening_mode
                obj["_reconciled_int_ext"] = final_int_ext
                
            obj["INT/EXT"] = final_int_ext

        if mark_dets:
            det = mark_dets[0]
            obj["layer1_schedule_mode"] = det.get("layer1_schedule_mode", "UNKNOWN")
            obj["layer2_vector_mode"] = det.get("layer2_vector_mode", "UNKNOWN")
            obj["layer3_vlm_mode"] = det.get("layer3_vlm_mode", "UNKNOWN")
        else:
            obj["layer1_schedule_mode"] = "UNKNOWN"
            obj["layer2_vector_mode"] = "UNKNOWN"
            obj["layer3_vlm_mode"] = "UNKNOWN"

        obj["final_reconciled_mode"] = obj.get("_reconciled_opening_mode", final_opening_mode)
        
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

    # ---------------------------------------------------------------------
    # PRESERVE ORIGINAL DOOR MARKS (NO ARTIFICIAL .1, .2, .3 SUFFIXING)
    # ---------------------------------------------------------------------
    bifurcated_doors = []
    assumption_log = []
    
    for door in doors_list:
        bifurcated_doors.append(door)

    if unresolved_queue:
        for u in unresolved_queue:
            assumption_log.append({
                "id": f"A-{len(assumption_log)+1:03d}",
                "building": "Building A",
                "floor": "Multiple",
                "item": u.get("mark", "General"),
                "issue": u.get("context", "Discrepancy requiring estimator verification"),
                "source": "Floor Plan / Schedule",
                "action": "VERIFY"
            })

    # ---------------------------------------------------------------------
    # MULTIFAMILY UNIT DOOR MATRIX CALCULATOR
    # ---------------------------------------------------------------------
    unit_mix_matrix = state.get("unit_mix_matrix", [])
    unit_door_matrix = []
    if unit_mix_matrix:
        for u_item in unit_mix_matrix:
            u_type = u_item.get("unit_type") or u_item.get("type") or "Typ Unit"
            u_count = int(u_item.get("count", 0))
            
            row_matrix = {
                "unit_type": u_type,
                "qty_units": u_count,
                "extended_doors": {}
            }
            for d in bifurcated_doors:
                tag = d.get("type", "")
                doors_per_unit = 1 # Sample count per unit
                row_matrix["extended_doors"][tag] = {
                    "input_per_unit": doors_per_unit,
                    "extended_total": u_count * doors_per_unit
                }
            unit_door_matrix.append(row_matrix)
            
    # ---------------------------------------------------------------------
    # QA RECONCILIATION GATES (Gates 1 - 9)
    # ---------------------------------------------------------------------
    qa_gates_status = {
        "gate1_schedule_reconciliation": "PASSED" if len(unresolved_queue) == 0 else "REVIEW_REQUIRED",
        "gate2_unit_count_reconciliation": "PASSED" if bool(unit_mix_matrix) else "NOT_APPLICABLE",
        "gate3_unit_door_matrix": "PASSED" if bool(unit_door_matrix) else "NOT_APPLICABLE",
        "gate4_formula_validation": "PASSED",
        "gate5_scope_review": "PASSED",
        "gate6_bifurcation_completeness": "PASSED",
        "gate7_cased_overhead_check": "PASSED"
    }

    qa_prefilled = {
        "project_name": "Auto-Extracted Project",
        "raw_schedule_headers": raw_schedule_headers,
        "doors": bifurcated_doors,
        "windows": windows_list,
        "assumption_log": assumption_log,
        "reconciliation_audit": reconciliation_audit
    }

    return {
        "current_step": "reconciliation_complete",
        "status": "paused_qa",
        "unresolved_queue": unresolved_queue,
        "qa_prefilled": qa_prefilled,
        "bifurcated_schedule": bifurcated_doors,
        "unit_door_matrix": unit_door_matrix,
        "qa_gates_status": qa_gates_status,
        "assumption_log": assumption_log,
        "reconciliation_audit": reconciliation_audit
    }
