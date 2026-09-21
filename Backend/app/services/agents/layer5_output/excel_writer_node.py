import os
import datetime
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from app.core.logging import logger
from app.services.graph.state import CostmateState
from app.config import settings

# Internal pipeline / debug metadata keys to exclude from all Excel sheets
EXCLUDED_PIPELINE_KEYS = {
    "needs_review", "is_borderline", "review_reason", "section", "reason",
    "reconciled", "_reconciled_opening_mode", "_reconciled_int_ext",
    "_schedule_type", "_schedule_opening_mode", "_is_ad_system", "excluded",
    "count", "type"
}

TAKEOFF_CALCULATED_KEYS = {
    "qty", "opening mode", "opening_mode", "int/ext", "int_ext",
    "takeoff notes", "takeoff_notes", "estimator notes", "comments"
}

def get_dict_val_case_insensitive(d: dict, target_key: str, default="") -> str:
    if not isinstance(d, dict) or not target_key:
        return default
    if target_key in d and d[target_key] is not None and str(d[target_key]).strip() != "":
        return d[target_key]
    tk_lower = str(target_key).lower().strip()
    for k, v in d.items():
        if str(k).lower().strip() == tk_lower and v is not None and str(v).strip() != "":
            return v
    # Specific fallback for mark / type
    if tk_lower in ["mark", "marks", "door mark", "door no", "number", "type", "id", "mark / type", "mark/type"]:
        for k in ["mark", "MARK", "type", "TYPE", "door_mark", "number", "_original_mark", "door no", "door mark"]:
            if k in d and d[k] and str(d[k]).strip() != "":
                return d[k]
    # Specific fallbacks for head, jamb, sill details
    if "head" in tk_lower or tk_lower in ["head", "detail head", "detail_head", "sections head", "sections_head", "head detail", "head/jamb"]:
        head_aliases = ["head", "HEAD", "Head", "Detail Head", "detail_head", "Sections Head", "detail head", "Head Detail", "Head/Jamb", "Detail - Head", "Detail (Head)"]
        for k in head_aliases:
            if k in d and d[k] and str(d[k]).strip() != "":
                return d[k]
        for k, v in d.items():
            if "head" in str(k).lower() and v and str(v).strip() != "":
                return v

    if "jamb" in tk_lower or tk_lower in ["jamb", "detail jamb", "detail_jamb", "sections jamb", "sections_jamb", "jamb detail"]:
        jamb_aliases = ["jamb", "JAMB", "Jamb", "Detail Jamb", "detail_jamb", "Sections Jamb", "detail jamb", "Jamb Detail", "Detail - Jamb", "Detail (Jamb)"]
        for k in jamb_aliases:
            if k in d and d[k] and str(d[k]).strip() != "":
                return d[k]
        for k, v in d.items():
            if "jamb" in str(k).lower() and v and str(v).strip() != "":
                return v

    if "sill" in tk_lower or tk_lower in ["sill", "detail sill", "detail_sill", "sections sill", "sections_sill", "sill detail"]:
        sill_aliases = ["sill", "SILL", "Sill", "Detail Sill", "detail_sill", "detail sill", "Sill Detail"]
        for k in sill_aliases:
            if k in d and d[k] and str(d[k]).strip() != "":
                return d[k]
        for k, v in d.items():
            if "sill" in str(k).lower() and v and str(v).strip() != "":
                return v

    return default

def get_raw_schedule_columns(items: list) -> list:
    """
    Returns only the original schedule column headers extracted from the uploaded PDF schedule.
    Excludes takeoff-calculated columns and internal debug pipeline keys.
    """
    if not items:
        return ["NUMBER", "DOOR TYPE", "DOOR MATERIAL", "FRAME MATERIAL", "HARDWARE SET"]
    
    raw_cols = []
    seen = set()
    
    for item in items:
        if isinstance(item, dict):
            for k in item.keys():
                kl = str(k).lower().strip()
                if kl in EXCLUDED_PIPELINE_KEYS or kl in TAKEOFF_CALCULATED_KEYS or k.startswith("_"):
                    continue
                if kl not in seen:
                    seen.add(kl)
                    raw_cols.append(k)
                    
    return raw_cols if raw_cols else ["NUMBER", "DOOR TYPE", "DOOR MATERIAL", "FRAME MATERIAL", "HARDWARE SET"]

def get_estimation_columns(raw_sched_cols: list) -> list:
    """
    Returns the column header sequence for the Estimation Sheet:
    1. Qty (Takeoff column)
    2. FLOOR / LEVEL (if not already present in raw schedule columns)
    3. LOCATION / ROOM NAME (if not already present in raw schedule columns)
    4. Opening mode
    5. Int/Ext
    6. All remaining raw schedule columns
    7. Takeoff Notes
    """
    has_floor = any("floor" in str(c).lower() or "level" in str(c).lower() for c in raw_sched_cols)
    has_loc = any("location" in str(c).lower() or "room" in str(c).lower() for c in raw_sched_cols)
    
    est_cols = ["Qty"]
    if not has_floor:
        est_cols.append("FLOOR / LEVEL")
    if not has_loc:
        est_cols.append("LOCATION")
        
    est_cols.extend(["Opening mode", "Int/Ext"])
    
    for col in raw_sched_cols:
        col_lower = str(col).lower().strip()
        if col_lower not in [c.lower().strip() for c in est_cols]:
            est_cols.append(col)
            
    if "Takeoff Notes" not in est_cols and "Estimator Notes" not in est_cols:
        est_cols.append("Takeoff Notes")
        
    return est_cols

def get_item_mark(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    for k, v in item.items():
        kl = str(k).lower().strip()
        if kl in ["mark", "type", "marks", "door mark", "door no", "door no.", "window mark", "window no", "window no.", "id", "mark / type", "mark/type", "number"]:
            if v and str(v).strip():
                return str(v).strip().upper()
    return ""

def get_item_location(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    loc_keys = ["location", "location name", "room", "room name", "room no", "room number", "room/location", "room / location", "room_name", "room_no", "space", "area", "d.location", "room_label", "LOCATION"]
    for k, v in item.items():
        if str(k).lower().strip() in [lk.lower() for lk in loc_keys]:
            val = str(v).strip() if v else ""
            if val and val.lower() not in ["unknown", "none", "n/a", ""]:
                return val
    for k, v in item.items():
        if ("location" in str(k).lower() or "room" in str(k).lower()) and v:
            val = str(v).strip()
            if val and val.lower() not in ["unknown", "none", "n/a", ""]:
                return val
    return ""

async def excel_writer_node(state: CostmateState) -> dict:
    logger.info("Excel Writer: Generating Takeoff Workbook with Clean Schedule & Estimation Sheets...")
    
    qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
    schedule_raw = state.get("schedule", {})
    
    doors = qa.get("doors") or schedule_raw.get("doors", []) or state.get("schedule_data", [])
    windows = qa.get("windows") or schedule_raw.get("windows", [])
    items = doors + windows
    
    proj_title = state.get("project_name") or "Costmate Project Takeoff"
    today_str = datetime.date.today().strftime("%d.%m.%Y")
    
    # Extract intake data settings from state or intake_data payload
    intake_data = state.get("intake_data") if isinstance(state.get("intake_data"), dict) else {}
    intake_settings = intake_data.get("globalSettings") if isinstance(intake_data.get("globalSettings"), dict) else {}
    
    building_type = str(
        state.get("building_type", "") or 
        intake_data.get("buildingType", "") or 
        intake_settings.get("buildingType", "")
    ).lower()
    
    cropped_unit_matrix = (
        state.get("unit_mix_matrix") or 
        state.get("unitMatrix") or 
        intake_data.get("unitMatrix") or 
        intake_data.get("unitMixMatrix") or 
        intake_settings.get("unitMatrix") or 
        intake_settings.get("unitMixMatrix")
    )
    cropped_unit_door_schedule = (
        state.get("unit_door_schedule") or 
        state.get("unitDoorSchedule") or 
        intake_data.get("unitDoorSchedule") or 
        intake_data.get("unitDoorScheduleData") or 
        intake_settings.get("unitDoorSchedule") or 
        intake_settings.get("unitDoorScheduleData")
    )

    is_apartment = (
        "apartment" in building_type or 
        "multi" in building_type or 
        bool(cropped_unit_matrix) or 
        bool(cropped_unit_door_schedule) or
        "apartment" in proj_title.lower()
    )
                    
    wb = openpyxl.Workbook()
    wb.remove(wb.active) # Remove default sheet
    
    # Core Fonts and Borders
    font_main = Font(name="Times New Roman", size=10)
    font_main_bold = Font(name="Times New Roman", size=10, bold=True)
    font_hdr_bold = Font(name="Times New Roman", size=11, bold=True)
    font_hdr_white = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    double_bottom = Border(
        top=Side(style='thin', color='000000'),
        bottom=Side(style='double', color='000000')
    )
    
    fill_yellow = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    fill_pink = PatternFill(start_color="FF00FF", end_color="FF00FF", fill_type="solid")
    fill_blue_ext = PatternFill(start_color="007FFF", end_color="007FFF", fill_type="solid")
    fill_green_soft = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
    fill_orange_win = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
    fill_pastel_blue = PatternFill(start_color="C6D9F0", end_color="C6D9F0", fill_type="solid")
    fill_navy_banner = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    
    # Determine Column Schemas
    raw_headers_input = qa.get("raw_schedule_headers") or get_raw_schedule_columns(items)
    raw_sched_cols = [c for c in raw_headers_input if str(c).lower().strip() not in EXCLUDED_PIPELINE_KEYS and not str(c).startswith("_")]
    est_cols = get_estimation_columns(raw_sched_cols)
    
    # Metadata Block
    meta_items = [
        (1, "PROJECT NAME:", proj_title),
        (2, "TAKEOFF DONE BY:", "Costmate AI Takeoff"),
        (3, "PLANS DATE:", "07.09.2026"),
        (4, "TAKEOFF DATE:", today_str)
    ]
    
    # -------------------------------------------------------------------------
    # SHEET 1: RAW SCHEDULE SHEET (Only Extracted Schedule Columns)
    # -------------------------------------------------------------------------
    ws_sched = wb.create_sheet(title="Schedule")
    ws_sched.freeze_panes = 'A6'
    
    for r_idx, label, val in meta_items:
        c1 = ws_sched.cell(row=r_idx, column=1, value=label)
        c1.font = font_main_bold
        c2 = ws_sched.cell(row=r_idx, column=2, value=val)
        c2.font = font_main
        c2.fill = fill_yellow
        
    for c_idx, h_text in enumerate(raw_sched_cols, 1):
        cell = ws_sched.cell(row=5, column=c_idx, value=h_text)
        cell.font = font_hdr_bold
        cell.fill = fill_navy_banner
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        
    s_row = 6
    for item in items:
        for c_idx, col_name in enumerate(raw_sched_cols, 1):
            val = get_dict_val_case_insensitive(item, col_name, "")
            cell = ws_sched.cell(row=s_row, column=c_idx, value=val if val is not None else "")
            cell.font = font_main
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        s_row += 1

    for col in ws_sched.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_sched.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # -------------------------------------------------------------------------
    # SHEET 2: ESTIMATION SHEET (Raw Schedule Columns + Takeoff Qty, Mode, Int/Ext, Notes)
    # -------------------------------------------------------------------------
    ws_est = wb.create_sheet(title="Estimation")
    ws_est.freeze_panes = 'A10'
    
    for r_idx, label, val in meta_items:
        c1 = ws_est.cell(row=r_idx, column=1, value=label)
        c1.font = font_main_bold
        c2 = ws_est.cell(row=r_idx, column=2, value=val)
        c2.font = font_main
        c2.fill = fill_yellow
        
    ws_est.cell(row=8, column=1, value="Door & Window Takeoff Estimation").font = Font(name="Times New Roman", size=12, bold=True)
    
    for c_idx, h_text in enumerate(est_cols, 1):
        cell = ws_est.cell(row=9, column=c_idx, value=h_text)
        cell.font = font_hdr_bold
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        
    # Group items floor by floor for estimation
    floors_dict = {}
    for item in items:
        fl = str(item.get("FLOOR / LEVEL", item.get("floor", item.get("level", "1ST FLOOR")))).strip().upper()
        if fl not in floors_dict:
            floors_dict[fl] = []
        floors_dict[fl].append(item)
        
    curr_row = 10
    for fl_name, fl_items in floors_dict.items():
        # Floor Banner Header
        ws_est.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=len(est_cols))
        b_cell = ws_est.cell(row=curr_row, column=1, value=fl_name)
        b_cell.font = font_hdr_white
        b_cell.fill = fill_navy_banner
        b_cell.alignment = Alignment(horizontal="left", vertical="center")
        curr_row += 1
        
        fl_start_row = curr_row
        for item in fl_items:
            door_mat = str(item.get("DOOR MATERIAL", item.get("door_material", ""))).strip()
            frame_mat = str(item.get("FRAME MATERIAL", item.get("frame_material", ""))).strip()
            ie_status = str(item.get("INT/EXT", item.get("_reconciled_int_ext", item.get("int_ext", "Interior"))))
            op_mode = str(item.get("Opening Mode", item.get("_reconciled_opening_mode", item.get("opening_mode", "Single"))))
            
            is_storefront = (door_mat == "-" or frame_mat == "-" or op_mode == "STOREFRONT" or ie_status == "Not in Scope")
            
            fill_color = None
            if is_storefront:
                fill_color = fill_pink
                op_mode = "STOREFRONT"
                ie_status = "Not in Scope"
            elif ie_status == "Exterior":
                fill_color = fill_blue_ext
            elif ie_status == "Soft Exterior":
                fill_color = fill_green_soft
            elif ie_status == "Window":
                fill_color = fill_orange_win
            else:
                fill_color = fill_yellow
                
            row_vals = []
            for col_name in est_cols:
                cn_lower = col_name.lower().strip()
                if cn_lower == "qty":
                    row_vals.append(item.get("qty", item.get("QTY", item.get("count", 1))))
                elif cn_lower in ["floor / level", "floor", "level"]:
                    row_vals.append(fl_name)
                elif cn_lower in ["location", "room name"]:
                    row_vals.append(get_item_location(item))
                elif cn_lower in ["opening mode", "opening_mode"]:
                    row_vals.append(op_mode)
                elif cn_lower in ["int/ext", "int_ext"]:
                    row_vals.append(ie_status)
                elif cn_lower in ["takeoff notes", "takeoff_notes", "estimator notes"]:
                    notes = item.get("Takeoff Notes", item.get("COMMENTS", ""))
                    if is_storefront and not notes:
                        notes = "SEE STOREFRONT SCHEDULE."
                    row_vals.append(notes)
                else:
                    row_vals.append(get_dict_val_case_insensitive(item, col_name, ""))
                    
            for c_idx, val in enumerate(row_vals, 1):
                cell = ws_est.cell(row=curr_row, column=c_idx, value=val if val is not None else "")
                cell.font = font_main
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center", vertical="center")
                # Highlight Door Mark column or NUMBER column
                if est_cols[c_idx-1].lower().strip() in ["number", "mark", "door mark", "door no", "type"] and fill_color:
                    cell.fill = fill_color
            curr_row += 1
            
        # Floor Subtotal
        c_sub1 = ws_est.cell(row=curr_row, column=1, value=f"=SUM(A{fl_start_row}:A{curr_row-1})")
        c_sub1.font = font_main_bold
        c_sub1.border = double_bottom
        c_sub2 = ws_est.cell(row=curr_row, column=2, value=f"{fl_name} TOTAL")
        c_sub2.font = font_main_bold
        c_sub2.border = double_bottom
        curr_row += 2

    for col in ws_est.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_est.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # -------------------------------------------------------------------------
    # SHEET 3, 4, 5 (If Multi-Family): Unit Count, Unit Door Matrix & Unit Door TO
    # -------------------------------------------------------------------------
    if is_apartment:
        return build_multifamily_sheets(
            wb, state, meta_items, font_main, font_main_bold, font_hdr_bold,
            thin_border, double_bottom, fill_yellow, fill_green_soft, fill_pastel_blue, fill_navy_banner,
            cropped_unit_matrix=cropped_unit_matrix, cropped_unit_door_schedule=cropped_unit_door_schedule
        )

    clean_proj_name = "".join(c for c in proj_title if c.isalnum() or c in [' ', '_', '-']).strip().replace(' ', '_')
    file_name = f"{clean_proj_name}_Division8_Takeoff_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(settings.OUTPUT_DIR, file_name)
    wb.save(file_path)
    logger.info(f"Excel Takeoff saved cleanly at {file_path}")
    return {"excel_file_path": file_path, "status": "completed", "current_step": "completed"}

def build_multifamily_sheets(
    wb, state, meta_items, font_main, font_main_bold, font_hdr_bold,
    thin_border, double_bottom, fill_yellow, fill_green_soft, fill_pastel_blue, fill_navy_banner,
    cropped_unit_matrix=None, cropped_unit_door_schedule=None
):
    proj_title = state.get("project_name") or "Costmate Project Takeoff"

    # Color Fills Mapping based on Int/Ext Classification
    fill_cyan_ext = PatternFill(start_color="00B0F0", end_color="00B0F0", fill_type="solid")
    fill_orange_win = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
    fill_pink_scope = PatternFill(start_color="FF69B4", end_color="FF69B4", fill_type="solid")

    def get_tag_fill_color(ie_val: str):
        v = str(ie_val).lower().strip()
        if "ext" in v or "exterior" in v:
            return fill_cyan_ext
        elif "soft" in v:
            return fill_green_soft
        elif "win" in v or "window" in v:
            return fill_orange_win
        elif "not" in v or "pink" in v or "storefront" in v:
            return fill_pink_scope
        return fill_yellow

    # Handle Missing / Optional Dataset cleanly without synthetic fallbacks
    if not cropped_unit_matrix or not isinstance(cropped_unit_matrix, list) or len(cropped_unit_matrix) == 0:
        logger.info("No Unit Matrix table was uploaded. Saving clean Schedule & Estimation sheets only.")
        clean_proj_name = "".join(c for c in proj_title if c.isalnum() or c in [' ', '_', '-']).strip().replace(' ', '_')
        file_name = f"{clean_proj_name}_Division8_Takeoff_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        file_path = os.path.join(settings.OUTPUT_DIR, file_name)
        wb.save(file_path)
        return {"excel_file_path": file_path, "status": "completed", "current_step": "completed"}

    # --- Parse Real Unit Matrix ---
    # Find floor/level columns in cropped_unit_matrix (exclude UNIT, NAME, TYPE, AREA, TOTAL, CARE)
    sample_row = cropped_unit_matrix[0] if len(cropped_unit_matrix) > 0 else {}
    non_floor_keys = {"unit", "name", "type", "unit_type", "unit type", "area", "sqft", "sf", "area (sf)", "care", "category", "total", "total units", "units"}
    
    floor_cols = []
    unit_key = "UNIT"
    area_key = "AREA"
    care_key = "CARE"

    for k in sample_row.keys():
        kl = str(k).lower().strip()
        if kl in ["unit", "name", "type", "unit_type", "unit type"]:
            unit_key = k
        elif kl in ["area", "sqft", "sf", "area (sf)"]:
            area_key = k
        elif kl in ["care", "category"]:
            care_key = k
        elif kl not in non_floor_keys and not kl.startswith("_"):
            floor_cols.append(k)

    if not floor_cols:
        floor_cols = ["1ST FLR", "2ND FLR", "3RD FLR"]

    # -------------------------------------------------------------------------
    # SHEET 3: Unit Count
    # -------------------------------------------------------------------------
    ws_uc = wb.create_sheet(title="Unit Count")
    for r_idx, label, val in meta_items:
        ws_uc.cell(row=r_idx, column=1, value=label).font = font_main_bold
        ws_uc.cell(row=r_idx, column=2, value=val).fill = fill_yellow
    
    ws_uc.cell(row=4, column=1, value="Unit Count Matrix").font = Font(name="Times New Roman", size=11, bold=True)
    uc_headers = ["Care / Category", "Unit Type", "Area (SF)"] + floor_cols + ["Total Units"]
    for c_idx, h_text in enumerate(uc_headers, 1):
        cell = ws_uc.cell(row=5, column=c_idx, value=h_text)
        cell.font = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
        cell.fill = fill_navy_banner
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        
    u_row = 6
    parsed_unit_rows = []

    for u_item in cropped_unit_matrix:
        ut_val = str(u_item.get(unit_key, u_item.get("UNIT", u_item.get("unit_type", f"Unit {u_row-5}")))).strip()
        care_val = str(u_item.get(care_key, u_item.get("care", "Multi-Family"))).strip()
        area_val = u_item.get(area_key, u_item.get("AREA", 800))
        
        ws_uc.cell(row=u_row, column=1, value=care_val).border = thin_border
        ws_uc.cell(row=u_row, column=2, value=ut_val).border = thin_border
        ws_uc.cell(row=u_row, column=3, value=area_val).border = thin_border
        
        row_floor_sum = 0
        for f_idx, f_col in enumerate(floor_cols, 4):
            raw_f_val = u_item.get(f_col, 0)
            try:
                f_val = int(float(str(raw_f_val).replace(",", "").strip())) if str(raw_f_val).strip() != "" else 0
            except Exception:
                f_val = 0
            ws_uc.cell(row=u_row, column=f_idx, value=f_val).border = thin_border
            row_floor_sum += f_val
            
        last_floor_let = get_column_letter(len(floor_cols) + 3)
        tot_col_let = get_column_letter(len(floor_cols) + 4)
        
        # Openpyxl formula for Total Units
        c_tot = ws_uc.cell(row=u_row, column=len(floor_cols) + 4, value=f"=SUM(D{u_row}:{last_floor_let}{u_row})")
        c_tot.font = font_main_bold
        c_tot.border = thin_border
        
        parsed_unit_rows.append({
            "care": care_val,
            "unit_type": ut_val,
            "area": area_val,
            "total_units": row_floor_sum,
            "uc_row_idx": u_row
        })
        u_row += 1

    for col in ws_uc.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_uc.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # --- Parse Real Unit Door Schedule / Tags ---
    door_tags = []
    tag_metadata = []

    if cropped_unit_door_schedule and isinstance(cropped_unit_door_schedule, list) and len(cropped_unit_door_schedule) > 0:
        # User uploaded explicit Unit Door Schedule
        for idx, d in enumerate(cropped_unit_door_schedule):
            mark_name = str(d.get("mark", d.get("MARK", d.get("NUMBER", d.get("NUMBER", f"RES-{idx+1}"))))).upper().strip()
            door_tags.append(mark_name)
            tag_metadata.append({
                "mark": mark_name,
                "partition": str(d.get("partition", d.get("wall_partition", d.get("PARTITION", "PP6a")))).strip(),
                "mode": str(d.get("mode", d.get("opening_mode", d.get("MODE", "SGL")))).strip(),
                "location": str(d.get("location", d.get("LOCATION", "BATH"))).strip(),
                "int_ext": str(d.get("int_ext", d.get("INT/EXT", "Interior"))).strip()
            })
    else:
        # Look for door tags as keys in cropped_unit_matrix
        for k in sample_row.keys():
            kl = str(k).upper().strip()
            if kl.startswith("RES") or kl.startswith("D-") or kl.startswith("D") and len(kl) <= 6:
                door_tags.append(kl)
                tag_metadata.append({
                    "mark": kl, "partition": "STD", "mode": "SGL", "location": "UNIT", "int_ext": "Interior"
                })

    if not door_tags:
        door_tags = ["RES-1", "RES-2", "RES-3"]
        tag_metadata = [
            {"mark": "RES-1", "partition": "PP6a", "mode": "SLD", "location": "BATH", "int_ext": "Interior"},
            {"mark": "RES-2", "partition": "RS61", "mode": "SGL", "location": "BEDROOM", "int_ext": "Interior"},
            {"mark": "RES-3", "partition": "PP6a", "mode": "BIFOLD", "location": "CLOSET", "int_ext": "Interior"}
        ]

    # -------------------------------------------------------------------------
    # SHEET 4: Unit Door Matrix (Stage 1: Per-Unit Composition)
    # -------------------------------------------------------------------------
    ws_udm = wb.create_sheet(title="Unit Door Matrix")
    for r_idx, label, val in meta_items:
        ws_udm.cell(row=r_idx, column=1, value=label).font = font_main_bold
        ws_udm.cell(row=r_idx, column=2, value=val).fill = fill_yellow

    udm_headers = ["Care", "Unit Type", "Area (SF)", "Total Units"] + door_tags + ["TOTAL DOORS PER UNIT"]

    for c_idx, h_text in enumerate(udm_headers, 1):
        cell = ws_udm.cell(row=5, column=c_idx, value=h_text)
        cell.font = font_hdr_bold
        cell.fill = fill_pastel_blue
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Build matrix lookup from cropped_unit_door_schedule or cropped_unit_matrix
    matrix_lookup = {}
    if cropped_unit_door_schedule and isinstance(cropped_unit_door_schedule, list):
        for item in cropped_unit_door_schedule:
            if isinstance(item, dict):
                ut_key = str(item.get("unit_type", item.get("UNIT", item.get("unit", "")))).upper().strip()
                if ut_key:
                    matrix_lookup[ut_key] = item

    m_row = 6
    for pu in parsed_unit_rows:
        ut = pu["unit_type"]
        uc_row_idx = pu["uc_row_idx"]
        
        ws_udm.cell(row=m_row, column=1, value=pu["care"]).border = thin_border
        ws_udm.cell(row=m_row, column=2, value=ut).border = thin_border
        ws_udm.cell(row=m_row, column=3, value=pu["area"]).border = thin_border
        
        # Formula reference to Unit Count
        c_u = ws_udm.cell(row=m_row, column=4, value=f"='Unit Count'!{get_column_letter(len(floor_cols) + 4)}{uc_row_idx}")
        c_u.border = thin_border
        
        unit_counts_dict = matrix_lookup.get(str(ut).upper().strip(), {})
        # Find matching row in cropped_unit_matrix if not in schedule
        if not unit_counts_dict:
            for um_item in cropped_unit_matrix:
                if str(um_item.get(unit_key, um_item.get("UNIT", ""))).upper().strip() == str(ut).upper().strip():
                    unit_counts_dict = um_item
                    break

        row_doors_sum = 0
        for dt_idx, dt in enumerate(door_tags, 5):
            raw_d_cnt = unit_counts_dict.get(dt, unit_counts_dict.get(dt.lower(), 1))
            try:
                d_cnt = int(float(str(raw_d_cnt).replace(",", "").strip())) if str(raw_d_cnt).strip() != "" else 0
            except Exception:
                d_cnt = 0
            ws_udm.cell(row=m_row, column=dt_idx, value=d_cnt).border = thin_border
            row_doors_sum += d_cnt
        
        last_tag_letter = get_column_letter(len(door_tags) + 4)
        c_dtot = ws_udm.cell(row=m_row, column=len(door_tags) + 5, value=f"=SUM(E{m_row}:{last_tag_letter}{m_row})")
        c_dtot.font = font_main_bold
        c_dtot.border = thin_border
        m_row += 1

    # Bottom TAG TOTALS row for Matrix
    ws_udm.cell(row=m_row, column=1, value="TAG TOTALS").font = font_main_bold
    ws_udm.cell(row=m_row, column=1).border = double_bottom
    for dt_idx, dt in enumerate(door_tags, 5):
        dt_col_letter = get_column_letter(dt_idx)
        c_mgt = ws_udm.cell(row=m_row, column=dt_idx, value=f"=SUM({dt_col_letter}6:{dt_col_letter}{m_row-1})")
        c_mgt.font = font_main_bold
        c_mgt.border = double_bottom

    for col in ws_udm.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_udm.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # -------------------------------------------------------------------------
    # SHEET 5: Unit Door TO (Stage 2: Extended Project Takeoff)
    # -------------------------------------------------------------------------
    ws_udto = wb.create_sheet(title="Unit Door TO")
    
    # 3-Row Header Block
    for r_idx, label, val in meta_items:
        ws_udto.cell(row=r_idx, column=1, value=label).font = font_main_bold
        ws_udto.cell(row=r_idx, column=2, value=val).fill = fill_yellow

    ws_udto.cell(row=4, column=1, value="REPEATING UNIT DOOR TAKEOFF (SCHEDULED)").font = Font(name="Times New Roman", size=12, bold=True)
    
    # Row 5: Merged Tag Banners
    ws_udto.cell(row=5, column=1, value="Care").font = font_hdr_bold
    ws_udto.cell(row=5, column=2, value="Unit Type").font = font_hdr_bold
    ws_udto.cell(row=5, column=3, value="Qty Units").font = font_hdr_bold
    
    col_pos = 4
    ext_col_letters = []
    for tag_idx, tmeta in enumerate(tag_metadata):
        start_c = col_pos
        end_c = col_pos + 1
        ws_udto.merge_cells(start_row=5, start_column=start_c, end_row=5, end_column=end_c)
        banner_cell = ws_udto.cell(row=5, column=start_c, value=f"DOOR {tmeta['mark']} ({tmeta['partition']} / {tmeta['mode']} / {tmeta['location']})")
        banner_cell.font = font_hdr_bold
        banner_cell.fill = get_tag_fill_color(tmeta['int_ext'])
        banner_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        ws_udto.cell(row=6, column=start_c, value="Input").font = font_main_bold
        ws_udto.cell(row=6, column=start_c).alignment = Alignment(horizontal="center")
        ws_udto.cell(row=6, column=start_c).border = thin_border
        
        ws_udto.cell(row=6, column=end_c, value="Extended").font = font_main_bold
        ws_udto.cell(row=6, column=end_c).alignment = Alignment(horizontal="center")
        ws_udto.cell(row=6, column=end_c).fill = fill_pastel_blue
        ws_udto.cell(row=6, column=end_c).border = thin_border
        
        ext_col_letters.append(get_column_letter(end_c))
        col_pos += 2

    # Row 6 Sub-headers
    ws_udto.cell(row=6, column=1, value="Care").font = font_hdr_bold
    ws_udto.cell(row=6, column=2, value="Unit Type").font = font_hdr_bold
    ws_udto.cell(row=6, column=3, value="Qty Units").font = font_hdr_bold

    row_tot_col = col_pos
    ws_udto.cell(row=5, column=row_tot_col, value="Row Total").font = font_hdr_bold
    ws_udto.cell(row=6, column=row_tot_col, value="Row Total").font = font_hdr_bold

    to_row = 7
    for pu_idx, pu in enumerate(parsed_unit_rows, 6):
        ut = pu["unit_type"]
        tot_units = pu["total_units"]
        uc_row_idx = pu["uc_row_idx"]

        ws_udto.cell(row=to_row, column=1, value=pu["care"]).border = thin_border
        ws_udto.cell(row=to_row, column=2, value=ut).border = thin_border
        
        c_qu = ws_udto.cell(row=to_row, column=3, value=f"='Unit Count'!{get_column_letter(len(floor_cols) + 4)}{uc_row_idx}")
        c_qu.border = thin_border
        
        curr_c = 4
        for tag_idx, tmeta in enumerate(tag_metadata):
            matrix_tag_col = get_column_letter(tag_idx + 5)

            input_cell = ws_udto.cell(row=to_row, column=curr_c, value=f"='Unit Door Matrix'!{matrix_tag_col}{pu_idx}")
            input_cell.border = thin_border
            
            ext_cell = ws_udto.cell(row=to_row, column=curr_c + 1, value=f"=$C{to_row}*{get_column_letter(curr_c)}{to_row}")
            ext_cell.font = font_main
            ext_cell.fill = fill_pastel_blue
            ext_cell.border = thin_border
            
            curr_c += 2

        ext_sum_expr = ",".join([f"{l}{to_row}" for l in ext_col_letters])
        c_utot = ws_udto.cell(row=to_row, column=row_tot_col, value=f"=SUM({ext_sum_expr})")
        c_utot.font = font_main_bold
        c_utot.border = thin_border
        to_row += 1

    # Grand Total Row for Unit Door TO
    ws_udto.cell(row=to_row, column=1, value="TOTAL UNIT DOORS").font = font_main_bold
    ws_udto.cell(row=to_row, column=1).fill = fill_green_soft
    ws_udto.cell(row=to_row, column=1).border = double_bottom

    c_pos = 4
    for tag_idx, tmeta in enumerate(tag_metadata):
        in_let = get_column_letter(c_pos)
        ext_let = get_column_letter(c_pos + 1)
        
        c_in_gt = ws_udto.cell(row=to_row, column=c_pos, value=f"=SUM({in_let}7:{in_let}{to_row-1})")
        c_in_gt.font = font_main_bold
        c_in_gt.border = double_bottom
        
        c_ext_gt = ws_udto.cell(row=to_row, column=c_pos + 1, value=f"=SUM({ext_let}7:{ext_let}{to_row-1})")
        c_ext_gt.font = font_main_bold
        c_ext_gt.fill = fill_green_soft
        c_ext_gt.border = double_bottom
        
        c_pos += 2

    tot_col_letter = get_column_letter(row_tot_col)
    c_final = ws_udto.cell(row=to_row, column=row_tot_col, value=f"=SUM({tot_col_letter}7:{tot_col_letter}{to_row-1})")
    c_final.font = font_main_bold
    c_final.fill = fill_green_soft
    c_final.border = double_bottom

    for col in ws_udto.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_udto.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # Save to disk
    clean_proj_name = "".join(c for c in proj_title if c.isalnum() or c in [' ', '_', '-']).strip().replace(' ', '_')
    file_name = f"{clean_proj_name}_Division8_Takeoff_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
    
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(settings.OUTPUT_DIR, file_name)
    wb.save(file_path)
    logger.info(f"Excel Takeoff saved cleanly at {file_path}")
    
    return {"excel_file_path": file_path, "status": "completed", "current_step": "completed"}

