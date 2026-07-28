import os
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from app.services.graph.state import CostmateState
from app.core.logging import logger
from app.config import settings
from datetime import datetime

def set_border(ws, cell_range):
    thin = Side(border_style="thin", color="000000")
    border = Border(top=thin, left=thin, right=thin, bottom=thin)
    for row in ws[cell_range]:
        for cell in row:
            cell.border = border

def write_door_schedule(ws, instance_schedule):
    # Setup headers
    ws.merge_cells('A1:H1')
    ws['A1'] = "DOOR SCHEDULE"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    
    ws.merge_cells('C2:E2')
    ws['C2'] = "SIZE"
    ws['C2'].font = Font(bold=True)
    ws['C2'].alignment = Alignment(horizontal='center')
    
    headers2 = ['MARK', 'TYPE MARK', '', '', '', 'FIRE RATING', 'HARDWARE SET NO.', 'COMMENTS']
    headers3 = ['', '', 'WIDTH', 'HEIGHT', 'THICKNESS', '', '', '']
    
    for col, h in enumerate(headers2, 1):
        if h:
            ws.cell(row=2, column=col, value=h).font = Font(bold=True)
            ws.cell(row=2, column=col).alignment = Alignment(horizontal='center', vertical='center')
    
    for col, h in enumerate(headers3, 1):
        if h:
            ws.cell(row=3, column=col, value=h).font = Font(bold=True)
            ws.cell(row=3, column=col).alignment = Alignment(horizontal='center', vertical='center')
            
    ws.merge_cells('A2:A3')
    ws.merge_cells('B2:B3')
    ws.merge_cells('F2:F3')
    ws.merge_cells('G2:G3')
    ws.merge_cells('H2:H3')
    
    fill = PatternFill(start_color="EFEFEF", end_color="EFEFEF", fill_type="solid")
    
    row_idx = 4
    for inst in instance_schedule:
        ws.cell(row=row_idx, column=1, value=inst.get('mark', ''))
        ws.cell(row=row_idx, column=2, value=inst.get('type', ''))
        ws.cell(row=row_idx, column=3, value=inst.get('width', ''))
        ws.cell(row=row_idx, column=4, value=inst.get('height', ''))
        ws.cell(row=row_idx, column=5, value=inst.get('thickness', ''))
        ws.cell(row=row_idx, column=6, value=inst.get('fire_rating', ''))
        ws.cell(row=row_idx, column=7, value=inst.get('hardware_set', ''))
        ws.cell(row=row_idx, column=8, value=inst.get('comments', ''))
        
        # Zebra striping
        if row_idx % 2 == 0:
            for col in range(1, 9):
                ws.cell(row=row_idx, column=col).fill = fill
        
        row_idx += 1
        
    set_border(ws, f"A1:H{row_idx-1}")
    
    # Auto-adjust column widths
    from openpyxl.utils import get_column_letter
    for col in ws.columns:
        max_length = 0
        try:
            column = get_column_letter(col[0].column)
        except Exception:
            continue
        for cell in col:
            try:
                if cell.value and len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = min(adjusted_width, 30)

def write_unit_matrix(ws, unit_matrix):
    occurrences = unit_matrix.get("occurrences_by_floor", {})
    door_counts = unit_matrix.get("door_counts_per_unit_type", {})
    
    floors = set()
    for u, f_dict in occurrences.items():
        floors.update(f_dict.keys())
    floors = sorted(list(floors))
    
    ws['A1'] = "UNIT MATRIX"
    ws['A1'].font = Font(bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2+len(floors))
    
    headers = ["UNIT/FLOOR"] + [f"{f} FLOOR" for f in floors] + ["TOTAL"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=2, column=c, value=h).font = Font(bold=True)
        ws.cell(row=2, column=c).alignment = Alignment(horizontal='center')
        
    row_idx = 3
    for u, f_dict in occurrences.items():
        ws.cell(row=row_idx, column=1, value=u)
        total = 0
        for c, f in enumerate(floors, 2):
            val = f_dict.get(f, 0)
            try:
                total += int(val)
            except:
                pass
            ws.cell(row=row_idx, column=c, value=val).alignment = Alignment(horizontal='center')
        ws.cell(row=row_idx, column=2+len(floors), value=total).alignment = Alignment(horizontal='center')
        row_idx += 1
        
    set_border(ws, f"A1:{openpyxl.utils.get_column_letter(2+len(floors))}{row_idx-1}")
        
    # Door Matrix
    row_idx += 2
    start_row = row_idx
    
    all_doors = set()
    for u, d_dict in door_counts.items():
        all_doors.update(d_dict.keys())
    all_doors = sorted(list(all_doors))
    
    ws.cell(row=row_idx, column=1, value="UNIT DOOR MATRIX").font = Font(bold=True)
    ws.cell(row=row_idx, column=1).alignment = Alignment(horizontal='center')
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=2+len(all_doors))
    row_idx += 1
    
    d_headers = ["UNIT/FLOOR"] + all_doors + ["TOTAL"]
    for c, h in enumerate(d_headers, 1):
        ws.cell(row=row_idx, column=c, value=h).font = Font(bold=True)
        ws.cell(row=row_idx, column=c).alignment = Alignment(horizontal='center')
        
    row_idx += 1
    for u, d_dict in door_counts.items():
        ws.cell(row=row_idx, column=1, value=u)
        total = 0
        for c, d in enumerate(all_doors, 2):
            val = d_dict.get(d, 0)
            try:
                total += int(val)
            except:
                pass
            ws.cell(row=row_idx, column=c, value=val).alignment = Alignment(horizontal='center')
        ws.cell(row=row_idx, column=2+len(all_doors), value=total).alignment = Alignment(horizontal='center')
        row_idx += 1
        
    set_border(ws, f"A{start_row}:{openpyxl.utils.get_column_letter(2+len(all_doors))}{row_idx-1}")

def excel_writer_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"[{session_id}] Writing Doors and Windows to Excel...")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"costmate_doors_windows_{timestamp}.xlsx"
    file_path = os.path.join(settings.OUTPUT_DIR, filename)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    
    wb = openpyxl.Workbook()
    schedule_registry = None
    if "intake_data" in state and isinstance(state["intake_data"], dict):
        schedule_registry = state["intake_data"].get("globalSettings", {}).get("scheduleRegistry")
        
    has_instance = schedule_registry and schedule_registry.get("instance_schedule")
    has_unit = schedule_registry and schedule_registry.get("unit_matrix", {}).get("present")
    
    if has_instance or has_unit:
        if has_instance:
            ws = wb.active
            ws.title = "Door Schedule"
            write_door_schedule(ws, schedule_registry.get("instance_schedule"))
            
            if has_unit:
                ws2 = wb.create_sheet("Unit Matrix")
                write_unit_matrix(ws2, schedule_registry.get("unit_matrix"))
        else:
            ws = wb.active
            ws.title = "Unit Matrix"
            write_unit_matrix(ws, schedule_registry.get("unit_matrix"))
    else:
        # Basic Fallback
        qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
        ws = wb.active
        ws.title = "Doors and Windows"
        
        bold_font = Font(bold=True)
        headers = ["Type", "Width (m)", "Height (m)", "Material", "Count"]
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = bold_font
            
        current_row = 2
        for d in qa.get("doors", []):
            ws.cell(row=current_row, column=1, value=d.get("type", "Door"))
            ws.cell(row=current_row, column=2, value=d.get("width_m", 0))
            ws.cell(row=current_row, column=3, value=d.get("height_m", 0))
            ws.cell(row=current_row, column=4, value=d.get("frame_material", d.get("material", "")))
            ws.cell(row=current_row, column=5, value=d.get("count", 0))
            current_row += 1
            
        for w in qa.get("windows", []):
            ws.cell(row=current_row, column=1, value=w.get("type", "Window"))
            ws.cell(row=current_row, column=2, value=w.get("width_m", 0))
            ws.cell(row=current_row, column=3, value=w.get("height_m", 0))
            ws.cell(row=current_row, column=4, value=w.get("material", ""))
            ws.cell(row=current_row, column=5, value=w.get("count", 0))
            current_row += 1
            
    wb.save(file_path)
    
    return {
        "excel_file_path": file_path,
        "status": "completed",
        "current_step": "completed",
        "progress_pct": 100
    }
