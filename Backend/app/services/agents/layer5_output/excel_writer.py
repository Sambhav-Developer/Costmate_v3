import os
import openpyxl
from rapidfuzz import process, fuzz
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from app.core.logging import logger
from app.config import settings
from datetime import datetime

class ExcelAgent:
    def __init__(self):
        self.pink_fill = PatternFill(start_color="FFC0CB", end_color="FFC0CB", fill_type="solid")
        self.gray_fill = PatternFill(start_color="EFEFEF", end_color="EFEFEF", fill_type="solid")
        self.yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
        self.thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
    def _match_mark(self, plan_mark: str, schedule_marks: list) -> str:
        """Fuzzy match plan MARK to schedule MARK."""
        if not plan_mark or not schedule_marks:
            return None
        match = process.extractOne(plan_mark, schedule_marks, scorer=fuzz.ratio)
        if match and match[1] > 80:
            return match[0]
        return None

    def process_takeoff(self, schedule_data: list, door_instances: list, output_dir: str = None) -> str:
        """
        Fuses schedule and plan instances, calculates QTY, and writes Excel.
        """
        logger.info("ExcelAgent: Starting fusion and writing...")
        
        # 1. Group plan instances by matched MARK and Floor
        schedule_mark_dict = {str(r.get("mark", "")).strip().upper(): r for r in schedule_data}
        available_marks = list(schedule_mark_dict.keys())
        
        compiled_rows = []
        
        # Track which instances belong to which schedule MARK
        plan_matched = []
        unmatched_plan = []
        
        for inst in door_instances:
            mark = str(inst.get("mark", "")).strip().upper()
            matched_mark = self._match_mark(mark, available_marks)
            if matched_mark:
                plan_matched.append({"inst": inst, "schedule_mark": matched_mark})
            else:
                unmatched_plan.append(inst)
                
        # 2. Build rows
        for mark, sched_row in schedule_mark_dict.items():
            matching_insts = [p["inst"] for p in plan_matched if p["schedule_mark"] == mark]
            
            qty = len(matching_insts)
            floors = sorted(list(set(str(i.get("floor_no", "")) for i in matching_insts if i.get("floor_no"))))
            int_ext = sorted(list(set(str(i.get("int_ext", "")) for i in matching_insts if i.get("int_ext"))))
            opening_modes = sorted(list(set(str(i.get("opening_mode", "")) for i in matching_insts if i.get("opening_mode"))))
            
            # Storefront rule (Agent 7 processing rule)
            material = str(sched_row.get("MATERIAL", "")).upper()
            is_storefront = "ALUMINUM" in material or "GLASS" in material
            notes = sched_row.get("COMMENTS", "") or ""
            if is_storefront:
                notes = "STOREFRONT - " + str(notes)
                
            compiled_rows.append({
                "MARK": mark,
                "QTY": qty,
                "FLOOR NO": ", ".join(floors),
                "LOCATION": "Various" if qty > 1 else "Specific",
                "OPENING MODE": ", ".join(opening_modes),
                "INT/EXT": ", ".join(int_ext),
                "WIDTH": sched_row.get("DOOR WIDTH", ""),
                "HEIGHT": sched_row.get("HEIGHT", ""),
                "THICKNESS": sched_row.get("THICKNESS", ""),
                "MATERIAL": sched_row.get("MATERIAL", ""),
                "FINISH": sched_row.get("FINISH", ""),
                "FRAME MATERIAL": sched_row.get("FRAME MATERIAL", ""),
                "FRAME TYPE": sched_row.get("FRAME TYPE", ""),
                "FIRE RATING": sched_row.get("FIRE RATING", ""),
                "HARDWARE SET": sched_row.get("HARDWARE SET", ""),
                "ESTIMATOR NOTES": notes.strip(" -"),
                "_is_storefront": is_storefront,
                "_is_unmatched": False
            })
            
        # Add unmatched plan marks as flagged rows
        for inst in unmatched_plan:
             compiled_rows.append({
                "MARK": f"{inst.get('mark')} (UNMATCHED)",
                "QTY": 1,
                "FLOOR NO": str(inst.get("floor_no", "")),
                "LOCATION": "Unknown",
                "OPENING MODE": inst.get("opening_mode", ""),
                "INT/EXT": inst.get("int_ext", ""),
                "ESTIMATOR NOTES": "Found on plan, missing in schedule",
                "_is_storefront": False,
                "_is_unmatched": True
            })

        # 3. Write to Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Door Takeoff"
        
        headers = [
            "MARK", "QTY", "FLOOR NO", "LOCATION", "OPENING MODE", "INT/EXT",
            "WIDTH", "HEIGHT", "THICKNESS", "MATERIAL", "FINISH", 
            "FRAME MATERIAL", "FRAME TYPE", "FIRE RATING", "HARDWARE SET", "ESTIMATOR NOTES"
        ]
        
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = self.thin_border
            
        row_idx = 2
        for row_data in compiled_rows:
            for col, h in enumerate(headers, 1):
                val = row_data.get(h, "")
                cell = ws.cell(row=row_idx, column=col, value=val)
                cell.border = self.thin_border
                
                # Apply conditional formatting rules
                if row_data.get("_is_unmatched"):
                    cell.fill = self.yellow_fill
                elif row_data.get("_is_storefront"):
                    cell.fill = self.pink_fill
                elif row_idx % 2 == 0:
                    cell.fill = self.gray_fill
            row_idx += 1
            
        # Auto-adjust column widths
        from openpyxl.utils import get_column_letter
        for col in ws.columns:
            max_length = 0
            try:
                column = get_column_letter(col[0].column)
            except Exception:
                continue
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[column].width = min(max_length + 2, 40)
            
        if not output_dir:
            output_dir = os.path.join(settings.BASE_DIR, "assets", "outputs")
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"door_takeoff_{timestamp}.xlsx"
        filepath = os.path.join(output_dir, filename)
        
        wb.save(filepath)
        logger.info(f"ExcelAgent: File saved to {filepath}")
        return filepath

excel_agent = ExcelAgent()

async def excel_writer_node(state: dict) -> dict:
    """Wrapper for LangGraph to invoke the ExcelAgent."""
    logger.info("Executing excel_writer_node...")
    # In a fully wired graph, we would pass state["schedule_registry"]["rows"] and state["plan_extractions"]["instances"]
    # For now, just a stub to prevent ImportError in the legacy graph setup.
    return {"current_step": "completed", "progress_pct": 100}

