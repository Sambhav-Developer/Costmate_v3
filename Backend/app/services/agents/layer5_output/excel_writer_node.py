import os
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from app.core.logging import logger
from app.services.graph.state import CostmateState
from app.config import settings
from app.services.agents.layer2_vision.cv_detector_node import normalize_opening_mode

def get_item_mark(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    for k, v in item.items():
        kl = str(k).lower().strip()
        if kl in ["mark", "type", "marks", "door mark", "door no", "door no.", "window mark", "window no", "window no.", "id", "mark / type", "mark/type"]:
            if v and str(v).strip():
                return str(v).strip().upper()
    for k, v in item.items():
        kl = str(k).lower().strip()
        if ("mark" in kl or "type" in kl) and kl not in ["hardware group no", "door type", "frame type", "opening mode", "type of door", "type of frame"]:
            if v and str(v).strip():
                return str(v).strip().upper()
    return ""

async def excel_writer_node(state: CostmateState) -> dict:
    logger.info("Excel Writer: Generating Final Schedule (RAW + ESTIMATION)...")
    
    qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
    schedule_raw = state.get("schedule", {})
    specifications_insights = state.get("specifications_insights") or {}
    
    # Construct a concise spec notes summary from structured insights
    spec_notes = ""
    if specifications_insights:
        notes_list = []
        exclusions = specifications_insights.get("exclusions", [])
        if exclusions:
            notes_list.append(f"Exclusions: {', '.join(exclusions)}")
        defaults = specifications_insights.get("door_defaults", {})
        if defaults:
            def_parts = [f"{k}: {v}" for k, v in defaults.items() if v]
            if def_parts:
                notes_list.append(f"Defaults: {', '.join(def_parts)}")
        features = specifications_insights.get("special_features", [])
        if features:
            notes_list.append(f"Spec Rules: {'; '.join(features)}")
        spec_notes = " | ".join(notes_list)
            
    doors = qa.get("doors")
    if not doors:
        doors = schedule_raw.get("doors", [])
        
    windows = qa.get("windows")
    if not windows:
        windows = schedule_raw.get("windows", [])
        
    items = doors + windows
    if not items:
        items = state.get("schedule_data", [])
        if not doors and items:
            doors = items
    
    cv_results = state.get("cv_results", {})
    detections = cv_results.get("detections", [])
    cv_lookup = {str(d.get("mark", "")).strip().upper(): d for d in detections if d.get("mark")}
    
    wb = openpyxl.Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)
    
    if not items:
        ws = wb.create_sheet(title="No Data")
        ws.cell(row=1, column=1, value="No schedule data found.")
    else:
        def generate_raw_sheet(sheet_items, sheet_name):
            if not sheet_items: return
            
            all_keys = []
            for item in sheet_items:
                for k in item.keys():
                    if k not in all_keys:
                        all_keys.append(k)
            
            # Filter keys case-insensitively
            raw_headers = []
            for k in all_keys:
                kl = str(k).lower().strip()
                if kl not in ["count", "qty", "needs_review", "needs review", "need_review", "need review"]:
                    raw_headers.append(k)
            
            ws = wb.create_sheet(title=sheet_name)
            
            # Headers
            for col_num, header in enumerate(raw_headers, 1):
                display_header = "MARK" if str(header).lower() in ["type", "mark", "marks"] else str(header).upper()
                cell = ws.cell(row=1, column=col_num, value=display_header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.alignment = Alignment(horizontal="center")
                cell.fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = 18
 
            # Data
            for row_idx, item in enumerate(sheet_items, 2):
                for col_idx, key in enumerate(raw_headers, 1):
                    val = item.get(key, "")
                    ws.cell(row=row_idx, column=col_idx, value=str(val))
 
        def generate_estimation_sheet(sheet_items):
            if not sheet_items: return
            
            all_keys = []
            for item in sheet_items:
                for k in item.keys():
                    if k not in all_keys:
                        all_keys.append(k)
                        
            est_headers = ["QTY", "MARKS", "LOCATION", "ESTIMATOR NOTES", "FLOOR NO", "OPENING MODE", "INT/EXT"]
            dynamic_headers = []
            for k in all_keys:
                kl = str(k).lower().strip()
                if kl not in ["mark", "marks", "type", "count", "qty", "needs_review", "needs review", "need_review", "need review"]:
                    dynamic_headers.append(k)
                    
            final_headers = est_headers + dynamic_headers
            
            ws = wb.create_sheet(title="ESTIMATION SCHEDULE")
            wb.active = ws
            
            # Headers
            for col_num, header in enumerate(final_headers, 1):
                cell = ws.cell(row=1, column=col_num, value=str(header).upper())
                cell.font = Font(bold=True, color="FFFFFF")
                cell.alignment = Alignment(horizontal="center")
                cell.fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = 20
                
            # Data
            row_idx = 2
            for item in sheet_items:
                mark = get_item_mark(item)
                
                # Find all detected instances for this mark
                instances = [d for d in detections if str(d.get("mark", "")).strip().upper() == mark]
                
                # Determine material for Estimator Notes
                material = ""
                for k, v in item.items():
                    if "material" in str(k).lower():
                        material = str(v).upper()
                        break
                notes_parts = []
                is_alum_glass = any(kw in material for kw in ["ALUMINUM", "GLASS", "ALUMINIUM", "ALUM"]) or "AL" in [w.strip() for w in material.split()]
                if is_alum_glass:
                    notes_parts.append("Door is of Aluminium/Glass material.")
                    if spec_notes and any(kw in spec_notes.upper() for kw in ["EXCLUDE", "EXCLUDED"]):
                        notes_parts.append("EXCLUDED per specifications (Aluminium door exclusion).")
                notes = " | ".join(notes_parts)
                
                is_storefront = any(kw in material for kw in ["ALUMINUM", "GLASS", "ALUMINIUM", "ALUM"]) or "AL" in [w.strip() for w in material.split()]
                if instances:
                    # Write one row for each detected instance
                    for d in instances:
                        floor_no = d.get("floor_no", "")
                        if not floor_no:
                            for char in mark:
                                if char.isdigit():
                                    floor_no = char
                                    break
                                    
                        for col_idx, header in enumerate(final_headers, 1):
                            val = ""
                            if header == "QTY": val = "1"
                            elif header == "MARKS": val = mark
                            elif header == "LOCATION": val = d.get("location", "")
                            elif header == "ESTIMATOR NOTES": val = notes
                            elif header == "FLOOR NO": val = floor_no
                            elif header == "OPENING MODE": 
                                if is_storefront:
                                    val = ""
                                else:
                                    raw_mode = d.get("opening_mode", "SGL")
                                    val = normalize_opening_mode(raw_mode)
                            elif header == "INT/EXT": 
                                if is_storefront:
                                    val = ""
                                else:
                                    raw_ie = str(d.get("int_ext", "INT")).upper()
                                    if any(x in raw_ie for x in ["EXT", "EXTERNAL", "EXTERIOR"]):
                                        val = "EXT"
                                    else:
                                        val = "INT"
                            else: val = item.get(header, "")
                            
                            ws.cell(row=row_idx, column=col_idx, value=str(val))
                        row_idx += 1
                else:
                    # Write one placeholder row with QTY = 0 if not found in plan
                    floor_no = ""
                    for char in mark:
                        if char.isdigit():
                            floor_no = char
                            break
                            
                    for col_idx, header in enumerate(final_headers, 1):
                        val = ""
                        if header == "QTY": val = "0"
                        elif header == "MARKS": val = mark
                        elif header == "LOCATION": val = ""
                        elif header == "ESTIMATOR NOTES": val = notes
                        elif header == "FLOOR NO": val = floor_no
                        elif header == "OPENING MODE": val = ""
                        elif header == "INT/EXT": val = ""
                        else: val = item.get(header, "")
                        
                        ws.cell(row=row_idx, column=col_idx, value=str(val))
                    row_idx += 1

        if doors: generate_raw_sheet(doors, "DOOR SCHEDULE")
        if windows: generate_raw_sheet(windows, "WINDOW SCHEDULE")
        if items: generate_estimation_sheet(items)

    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(settings.OUTPUT_DIR, f"{state.get('session_id', 'output')}_schedule.xlsx")
    wb.save(file_path)
    
    logger.info(f"Excel file saved at {file_path}")
    return {"excel_file_path": file_path, "status": "completed", "current_step": "completed"}
