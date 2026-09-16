from app.services.agents.layer1_schedule.schedule_parser import schedule_parser_agent
from app.services.graph.state import CostmateState
from app.core.logging import logger

import re

def clean_door_mark(mark_str: str) -> str:
    if not mark_str:
        return ""
    # Strip watermarks/stamps (e.g. LANIGIRO, ORIGINAL, CONFIDENTIAL, COPY, DRAFT, WATERMARK, VOID)
    noise_words = [r"\bLANIGIRO\b", r"\bORIGINAL\b", r"\bWATERMARK\b", r"\bCONFIDENTIAL\b", r"\bCOPY\b", r"\bDRAFT\b", r"\bVOID\b", r"\bPRELIMINARY\b"]
    cleaned = mark_str.strip()
    for pattern in noise_words:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else mark_str.strip()

async def schedule_parser_node(state: CostmateState) -> dict:
    logger.info("Schedule Parser Node: Starting Track A")
    intake_data = state.get("intake_data") or {}
    global_settings = intake_data.get("globalSettings", {})
    
    # Try to extract schedule passed from frontend Step 1
    schedule_data = global_settings.get("scheduleRegistry") or global_settings.get("doorSchedule") or []
    
    # Extract the instance_schedule array if it's a complex dict (V1 prompt structure)
    if isinstance(schedule_data, dict):
        schedule_data = schedule_data.get("instance_schedule") or schedule_data.get("data") or []
        
    unique_rows = []
    if schedule_data and isinstance(schedule_data, list) and len(schedule_data) > 0:
        seen_marks = set()
        for row in schedule_data:
            if not isinstance(row, dict):
                unique_rows.append(row)
                continue
            mark_val = ""
            for k, v in row.items():
                if str(k).lower().strip() in ["mark", "type", "door mark", "door no", "door no.", "id", "mark / type", "mark/type"]:
                    mark_val = str(v).strip().upper()
                    break
            if not mark_val:
                for k, v in row.items():
                    if "mark" in str(k).lower() or "type" in str(k).lower():
                        mark_val = str(v).strip().upper()
                        break
            if mark_val:
                cleaned_mark = clean_door_mark(mark_val)
                if cleaned_mark != mark_val:
                    row["_original_mark"] = mark_val
                mark_val = cleaned_mark
                row["mark"] = mark_val
                if mark_val in seen_marks:
                    logger.info(f"Schedule Parser Node: Skipping duplicate row for mark {mark_val}")
                    continue
                seen_marks.add(mark_val)
            unique_rows.append(row)

            
    # Build SKILL.md schedule_sections (UNIQUE, REPEATING, OVERHEAD, CASED, WINDOW)
    unique_doors = []
    repeating_doors = []
    overhead_doors = []
    cased_openings = []
    windows = []
    
    for row in unique_rows:
        mark = str(row.get("mark", "")).upper().strip()
        loc = str(row.get("LOCATION", row.get("Location", row.get("Comments", "")))).lower()
        mode = str(row.get("Opening Mode", row.get("opening_mode", ""))).lower()
        notes = str(row.get("Takeoff Notes", row.get("COMMENTS", row.get("Comments", "")))).lower()
        
        if mark.startswith("OH") or "overhead" in loc or "roll-up" in loc or "coiling" in loc or "sectional" in loc or "overhead" in notes:
            row["section"] = "OVERHEAD"
            overhead_doors.append(row)
        elif mark.startswith("CO") or "cased" in loc or "cased opening" in notes or "frame only" in notes:
            row["section"] = "CASED"
            cased_openings.append(row)
        elif mark.startswith("W") or "window" in loc or "window" in notes:
            row["section"] = "WINDOW"
            windows.append(row)
        elif any(comm in loc for comm in ["lobby", "corridor", "stair", "mech", "elec", "trash", "garage", "amenity", "office", "mail", "laundry", "exit", "entry"]):
            row["section"] = "UNIQUE"
            unique_doors.append(row)
        else:
            row["section"] = "REPEATING"
            repeating_doors.append(row)
            
    schedule_sections = {
        "unique_doors": unique_doors,
        "repeating_doors": repeating_doors,
        "overhead_doors": overhead_doors,
        "cased_openings": cased_openings,
        "windows": windows
    }

    # Extract unit mix matrix if available in intake_data
    unit_mix_matrix = global_settings.get("unitMix") or global_settings.get("unitMixMatrix") or []

    logger.info(f"Schedule Parser Node: Categorized {len(unique_rows)} items -> UNIQUE: {len(unique_doors)}, REPEATING: {len(repeating_doors)}, OVERHEAD: {len(overhead_doors)}, CASED: {len(cased_openings)}, WINDOW: {len(windows)}")
    return {
        "schedule_data": unique_rows,
        "schedule_sections": schedule_sections,
        "unit_mix_matrix": unit_mix_matrix
    }

