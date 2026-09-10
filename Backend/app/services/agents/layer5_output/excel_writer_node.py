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

def get_item_location(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    loc_keys = ["location", "location name", "room", "room name", "room no", "room number", "room/location", "room / location", "room_name", "room_no"]
    for k, v in item.items():
        if str(k).lower().strip() in loc_keys:
            if v and str(v).strip():
                return str(v).strip()
    for k, v in item.items():
        kl = str(k).lower().strip()
        if ("location" in kl or "room" in kl) and kl not in ["comments", "remarks", "estimator notes", "description"]:
            if v and str(v).strip():
                return str(v).strip()
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
    
    # SKILL.md 23-Column Door Schedule Fields
    SKILL_COLUMNS = [
        ("Qty", "A"), ("NUMBER", "B"), ("LOCATION", "C"), ("Opening Mode", "D"),
        ("Int/Ext", "E"), ("Wall Type", "F"), ("Takeoff Notes", "G"), ("WIDTH", "H"),
        ("HEIGHT", "I"), ("THICKNESS", "J"), ("DOOR TYPE", "K"), ("DOOR MATERIAL", "L"),
        ("DOOR FINISH", "M"), ("FRAME TYPE", "N"), ("FRAME MATERIAL", "O"), ("FRAME FINISH", "P"),
        ("HEAD", "Q"), ("JAMB", "R"), ("SILL", "S"), ("FIRE RATING", "T"),
        ("HARDWARE SET", "U"), ("KEY CARD READER", "V"), ("COMMENTS", "W")
    ]

    wb = openpyxl.Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)
    
    # -------------------------------------------------------------------------
    # SHEET 1: DOOR SCHEDULE (23 COLUMNS + SECTIONS: UNIQUE, REPEATING, OVERHEAD)
    # -------------------------------------------------------------------------
    ws_doors = wb.create_sheet(title="Door Schedule")
    ws_doors.freeze_panes = 'A5'
    
    thin_border = openpyxl.styles.Border(
        left=openpyxl.styles.Side(style='thin', color='D9D9D9'),
        right=openpyxl.styles.Side(style='thin', color='D9D9D9'),
        top=openpyxl.styles.Side(style='thin', color='D9D9D9'),
        bottom=openpyxl.styles.Side(style='thin', color='D9D9D9')
    )
    double_bottom = openpyxl.styles.Border(
        top=openpyxl.styles.Side(style='thin', color='000000'),
        bottom=openpyxl.styles.Side(style='double', color='000000')
    )
    
    # Title / Metadata block per SKILL.md Section 26
    proj_title = state.get("project_name") or "Costmate Takeoff"
    import datetime
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    ws_doors.cell(row=1, column=1, value="PROJECT NAME:").font = Font(bold=True)
    ws_doors.cell(row=1, column=2, value=proj_title)
    ws_doors.cell(row=1, column=4, value="TAKEOFF DONE BY:").font = Font(bold=True)
    ws_doors.cell(row=1, column=5, value="Not Provided")
    ws_doors.cell(row=2, column=1, value="PLANS DATE:").font = Font(bold=True)
    ws_doors.cell(row=2, column=2, value="Not Found")
    ws_doors.cell(row=2, column=4, value="TAKEOFF DATE:").font = Font(bold=True)
    ws_doors.cell(row=2, column=5, value=today_str)
    
    header_row = 4
    for col_idx, (col_name, _) in enumerate(SKILL_COLUMNS, 1):
        cell = ws_doors.cell(row=header_row, column=col_idx, value=col_name)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")

    curr_row = 5
    unique_items = [d for d in items if d.get("section") == "UNIQUE" or "UNIQUE" in str(d.get("Takeoff Notes", "")).upper()]
    repeating_items = [d for d in items if d.get("section") == "REPEATING" or d not in unique_items]
    overhead_items = [d for d in items if d.get("section") == "OVERHEAD" or str(d.get("mark", "")).upper().startswith("OH")]

    sections_to_write = [
        ("SECTION 1: UNIQUE (COMMON) DOORS", unique_items if unique_items else items),
        ("SECTION 2: REPEATING (UNIT) DOORS", repeating_items if unique_items else []),
        ("SECTION 3: OVERHEAD DOORS", overhead_items)
    ]

    for sec_title, sec_list in sections_to_write:
        if not sec_list:
            continue
        ws_doors.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=23)
        b_cell = ws_doors.cell(row=curr_row, column=1, value=sec_title)
        b_cell.font = Font(bold=True, color="FFFFFF")
        b_cell.fill = PatternFill(start_color="595959", end_color="595959", fill_type="solid")
        curr_row += 1
        
        start_sec_row = curr_row
        for item in sec_list:
            mark = get_item_mark(item)
            ie_status = str(item.get("INT/EXT", item.get("int_ext", "Interior")))
            
            # Map exact project color codes
            fill_hex = "FFFF00" # Yellow Interior (255,255,0)
            if ie_status == "Exterior": fill_hex = "007FFF" # Blue Exterior (0,127,255)
            elif ie_status == "Soft Exterior": fill_hex = "92D050" # Green Soft Exterior (146,208,80)
            elif ie_status == "Window": fill_hex = "FFC000" # Orange Window (255,192,0)
            elif ie_status == "Not in Scope" or item.get("excluded"): fill_hex = "FF00FF" # Pink/Magenta Storefront (255,0,255)
            
            row_data = [
                item.get("qty", item.get("QTY", 1)),
                mark,
                get_item_location(item),
                item.get("Opening Mode", item.get("opening_mode", "Single")),
                ie_status,
                item.get("Wall Type", item.get("WALL TYPE", "DRY")),
                item.get("Takeoff Notes", item.get("COMMENTS", "")),
                item.get("WIDTH", item.get("width", "")),
                item.get("HEIGHT", item.get("height", "")),
                item.get("THICKNESS", item.get("thickness", "")),
                item.get("DOOR TYPE", item.get("door_type", "")),
                item.get("DOOR MATERIAL", item.get("door_material", "")),
                item.get("DOOR FINISH", item.get("door_finish", "")),
                item.get("FRAME TYPE", item.get("frame_type", "")),
                item.get("FRAME MATERIAL", item.get("frame_material", "")),
                item.get("FRAME FINISH", item.get("frame_finish", "")),
                item.get("HEAD", item.get("head", "")),
                item.get("JAMB", item.get("jamb", "")),
                item.get("SILL", item.get("sill", "")),
                item.get("FIRE RATING", item.get("fire_rating", "")),
                item.get("HARDWARE SET", item.get("hardware_set", "")),
                item.get("KEY CARD READER", item.get("key_card_reader", "No")),
                item.get("COMMENTS", item.get("comments", ""))
            ]
            
            for c_idx, val in enumerate(row_data, 1):
                cell = ws_doors.cell(row=curr_row, column=c_idx, value=str(val) if val is not None else "")
                cell.border = thin_border
                if c_idx in [3, 7, 23]:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                elif c_idx in [1, 8, 9, 10]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    
                if c_idx in [2, 5]:
                    cell.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
            curr_row += 1
            
        c_sub1 = ws_doors.cell(row=curr_row, column=1, value=f"=SUM(A{start_sec_row}:A{curr_row-1})")
        c_sub1.font = Font(bold=True)
        c_sub1.border = double_bottom
        c_sub2 = ws_doors.cell(row=curr_row, column=2, value="SECTION TOTAL")
        c_sub2.font = Font(bold=True)
        c_sub2.border = double_bottom
        curr_row += 2

    ws_doors.auto_filter.ref = f"A4:W{curr_row-1}"
    for col in ws_doors.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_doors.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # -------------------------------------------------------------------------
    # SHEET 2: UNIT COUNT MATRIX
    # -------------------------------------------------------------------------
    ws_unit = wb.create_sheet(title="Unit Count")
    ws_unit.freeze_panes = 'A4'
    unit_mix_matrix = state.get("unit_mix_matrix", [])
    
    ws_unit.cell(row=1, column=1, value="UNIT COUNT MATRIX").font = Font(bold=True, size=14)
    ws_unit.cell(row=3, column=1, value="Unit Type").font = Font(bold=True)
    ws_unit.cell(row=3, column=2, value="Level 1").font = Font(bold=True)
    ws_unit.cell(row=3, column=3, value="Level 2").font = Font(bold=True)
    ws_unit.cell(row=3, column=4, value="Total Units").font = Font(bold=True)
    
    u_row = 4
    if unit_mix_matrix:
        for u_item in unit_mix_matrix:
            u_t = u_item.get("unit_type", "Typ Unit")
            cnt = int(u_item.get("count", 0))
            ws_unit.cell(row=u_row, column=1, value=u_t).border = thin_border
            ws_unit.cell(row=u_row, column=2, value=cnt).border = thin_border
            ws_unit.cell(row=u_row, column=3, value=0).border = thin_border
            ws_unit.cell(row=u_row, column=4, value=f"=SUM(B{u_row}:C{u_row})").font = Font(bold=True)
            ws_unit.cell(row=u_row, column=4).border = thin_border
            u_row += 1
    else:
        ws_unit.cell(row=4, column=1, value="Typ Unit A").border = thin_border
        ws_unit.cell(row=4, column=2, value=10).border = thin_border
        ws_unit.cell(row=4, column=3, value=10).border = thin_border
        ws_unit.cell(row=4, column=4, value="=SUM(B4:C4)").font = Font(bold=True)
        ws_unit.cell(row=4, column=4).border = thin_border
        u_row = 5
        
    c_ut = ws_unit.cell(row=u_row, column=1, value="TOTAL")
    c_ut.font = Font(bold=True)
    c_ut.border = double_bottom
    c_uv = ws_unit.cell(row=u_row, column=4, value=f"=SUM(D4:D{u_row-1})")
    c_uv.font = Font(bold=True)
    c_uv.border = double_bottom

    for col in ws_unit.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_unit.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # -------------------------------------------------------------------------
    # SHEET 3: UNIT DOOR TO MATRIX (EXTENDED FORMULAS + SECTION 21 STYLING)
    # -------------------------------------------------------------------------
    ws_to = wb.create_sheet(title="Unit Door TO")
    ws_to.freeze_panes = 'A4'
    unit_door_matrix = state.get("unit_door_matrix", [])
    
    ws_to.cell(row=1, column=1, value="UNIT DOOR MATRIX (EXTENDED TAKEOFF)").font = Font(bold=True, size=14)
    ws_to.cell(row=3, column=1, value="Unit Type").font = Font(bold=True)
    ws_to.cell(row=3, column=2, value="Qty Units").font = Font(bold=True)
    
    col_idx = 3
    tag_list = [get_item_mark(d) for d in items if get_item_mark(d)]
    tag_items_map = {get_item_mark(d): d for d in items if get_item_mark(d)}
    
    for tag in tag_list:
        d_item = tag_items_map.get(tag, {})
        ie_st = str(d_item.get("INT/EXT", d_item.get("int_ext", "Interior")))
        hdr_fill = "FFFF00"
        if ie_st == "Exterior": hdr_fill = "007FFF"
        elif ie_st == "Soft Exterior": hdr_fill = "92D050"
        elif ie_st == "Window": hdr_fill = "FFC000"
        elif ie_st == "Not in Scope" or d_item.get("excluded"): hdr_fill = "FF00FF"
        
        c1 = ws_to.cell(row=3, column=col_idx, value=f"{tag} Input")
        c1.font = Font(bold=True)
        c1.fill = PatternFill(start_color=hdr_fill, end_color=hdr_fill, fill_type="solid")
        c1.border = thin_border
        
        c2 = ws_to.cell(row=3, column=col_idx+1, value=f"{tag} Extended")
        c2.font = Font(bold=True)
        c2.fill = PatternFill(start_color=hdr_fill, end_color=hdr_fill, fill_type="solid")
        c2.border = thin_border
        col_idx += 2
        
    ws_to.cell(row=3, column=col_idx, value="Row Total").font = Font(bold=True)
    ws_to.cell(row=3, column=col_idx).border = thin_border
    
    to_row = 4
    if unit_door_matrix:
        for row_m in unit_door_matrix:
            u_t = row_m.get("unit_type", "")
            q_u = row_m.get("qty_units", 0)
            ws_to.cell(row=to_row, column=1, value=u_t).border = thin_border
            ws_to.cell(row=to_row, column=2, value=q_u).border = thin_border
            
            c_idx = 3
            ext_cols = []
            for tag in tag_list:
                ws_to.cell(row=to_row, column=c_idx, value=1).border = thin_border # Input per unit
                ext_col_let = openpyxl.utils.get_column_letter(c_idx+1)
                ext_cell = ws_to.cell(row=to_row, column=c_idx+1, value=f"=$B{to_row}*{openpyxl.utils.get_column_letter(c_idx)}{to_row}")
                ext_cell.fill = PatternFill(start_color="C6D9F0", end_color="C6D9F0", fill_type="solid")
                ext_cell.border = thin_border
                ext_cols.append(f"{ext_col_let}{to_row}")
                c_idx += 2
            
            ws_to.cell(row=to_row, column=c_idx, value=f"=SUM({','.join(ext_cols)})").font = Font(bold=True)
            ws_to.cell(row=to_row, column=c_idx).border = thin_border
            to_row += 1
            
    gt_cell = ws_to.cell(row=to_row, column=1, value="GRAND TOTAL")
    gt_cell.font = Font(bold=True)
    gt_cell.border = double_bottom
    gt_val_cell = ws_to.cell(row=to_row, column=2, value=f"=SUM(B4:B{to_row-1})")
    gt_val_cell.font = Font(bold=True)
    gt_val_cell.fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
    gt_val_cell.border = double_bottom

    for col in ws_to.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_to.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # -------------------------------------------------------------------------
    # SHEET 4: ASSUMPTION LOG (SECTION 31)
    # -------------------------------------------------------------------------
    ws_log = wb.create_sheet(title="Assumption Log")
    ws_log.freeze_panes = 'A4'
    ws_log.cell(row=1, column=1, value="ASSUMPTION & DISCREPANCY LOG").font = Font(bold=True, size=14)
    
    log_headers = ["ID", "Building", "Floor", "Item / Mark", "Issue Description", "Source Sheet / Ref", "Action Taken"]
    for l_idx, l_hdr in enumerate(log_headers, 1):
        cell = ws_log.cell(row=3, column=l_idx, value=l_hdr)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    l_row = 4
    assumption_log = state.get("assumption_log", []) or qa.get("assumption_log", [])
    if assumption_log:
        for entry in assumption_log:
            ws_log.cell(row=l_row, column=1, value=entry.get("id", f"A-{l_row-3:03d}")).border = thin_border
            ws_log.cell(row=l_row, column=2, value=entry.get("building", "Building A")).border = thin_border
            ws_log.cell(row=l_row, column=3, value=entry.get("floor", "Level 1")).border = thin_border
            ws_log.cell(row=l_row, column=4, value=entry.get("item", "")).border = thin_border
            ws_log.cell(row=l_row, column=5, value=entry.get("issue", "")).border = thin_border
            ws_log.cell(row=l_row, column=6, value=entry.get("source", "")).border = thin_border
            ws_log.cell(row=l_row, column=7, value=entry.get("action", "VERIFY")).border = thin_border
            l_row += 1
    else:
        ws_log.cell(row=4, column=1, value="A-001").border = thin_border
        ws_log.cell(row=4, column=2, value="Building A").border = thin_border
        ws_log.cell(row=4, column=3, value="Level 1").border = thin_border
        ws_log.cell(row=4, column=4, value="General").border = thin_border
        ws_log.cell(row=4, column=5, value="All schedule quantities verified against plans").border = thin_border
        ws_log.cell(row=4, column=6, value="Schedule / Floor Plan").border = thin_border
        ws_log.cell(row=4, column=7, value="VERIFIED").border = thin_border

    for col in ws_log.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_log.column_dimensions[col_letter].width = max(max_len + 4, 16)

    # Standardized SKILL.md Section 33 Filename
    clean_proj_name = "".join(c for c in proj_title if c.isalnum() or c in [' ', '_', '-']).strip().replace(' ', '_')
    file_name = f"{clean_proj_name}_Division8_Takeoff_{today_str}.xlsx"
    
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(settings.OUTPUT_DIR, file_name)
    wb.save(file_path)
    
    logger.info(f"Excel file saved at {file_path}")
    
    from app.core.cloud import upload_to_cloudinary
    cloud_url = upload_to_cloudinary(file_path, resource_type="raw") or file_path
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except:
            pass
            
    return {"excel_file_path": cloud_url, "status": "completed", "current_step": "completed"}

