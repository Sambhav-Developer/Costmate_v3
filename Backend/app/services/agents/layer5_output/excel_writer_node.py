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
    if tk_lower in ["mark", "marks", "door mark", "door no", "number", "type"]:
        for k in ["mark", "MARK", "type", "TYPE", "door_mark", "number", "_original_mark"]:
            if k in d and d[k] and str(d[k]).strip() != "":
                return d[k]
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
    loc_keys = ["location", "location name", "room", "room name", "room no", "room number", "room/location", "room / location", "room_name", "room_no"]
    for k, v in item.items():
        if str(k).lower().strip() in loc_keys:
            if v and str(v).strip():
                return str(v).strip()
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
    
    building_type = str(state.get("building_type", "")).lower()
    is_apartment = ("apartment" in building_type or "multi" in building_type or 
                    bool(state.get("unit_mix_matrix")) or bool(state.get("unit_door_matrix")) or 
                    "apartment" in proj_title.lower())
                    
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
    # SHEET 3 (If Multi-Family): Unit Count & Unit Door-TO
    # -------------------------------------------------------------------------
    if is_apartment:
        ws_uc = wb.create_sheet(title="Unit Count")
        for r_idx, label, val in meta_items:
            ws_uc.cell(row=r_idx, column=1, value=label).font = font_main_bold
            ws_uc.cell(row=r_idx, column=2, value=val).fill = fill_yellow
        ws_uc.cell(row=4, column=4, value="Unit Count").font = Font(name="Times New Roman", size=11, bold=True)
        
        uc_headers = ["Unit/level", "Level 3", "Level 4", "Level 5", "Level 6", "Total"]
        for c_idx, h_text in enumerate(uc_headers, 4):
            cell = ws_uc.cell(row=5, column=c_idx, value=h_text)
            cell.font = font_hdr_bold
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border
            
        unit_mix = state.get("unit_mix_matrix") or [
            {"unit_type": "A1", "l3": 1, "l4": 1, "l5": 1, "l6": 0},
            {"unit_type": "A2", "l3": 1, "l4": 1, "l5": 1, "l6": 0},
            {"unit_type": "B1", "l3": 2, "l4": 2, "l5": 2, "l6": 1}
        ]
        u_row = 6
        for u_item in unit_mix:
            ut = u_item.get("unit_type", "A1")
            ws_uc.cell(row=u_row, column=4, value=ut).border = thin_border
            ws_uc.cell(row=u_row, column=5, value=u_item.get("l3", 1)).border = thin_border
            ws_uc.cell(row=u_row, column=6, value=u_item.get("l4", 1)).border = thin_border
            ws_uc.cell(row=u_row, column=7, value=u_item.get("l5", 1)).border = thin_border
            ws_uc.cell(row=u_row, column=8, value=u_item.get("l6", 0)).border = thin_border
            c_tot = ws_uc.cell(row=u_row, column=9, value=f"=SUM(E{u_row}:H{u_row})")
            c_tot.font = font_main_bold
            c_tot.border = thin_border
            u_row += 1

    # Save to disk
    clean_proj_name = "".join(c for c in proj_title if c.isalnum() or c in [' ', '_', '-']).strip().replace(' ', '_')
    file_name = f"{clean_proj_name}_Division8_Takeoff_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
    
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(settings.OUTPUT_DIR, file_name)
    wb.save(file_path)
    logger.info(f"Excel Takeoff saved cleanly at {file_path}")
    
    return {"excel_file_path": file_path, "status": "completed", "current_step": "completed"}
