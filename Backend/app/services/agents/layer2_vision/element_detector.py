import json
import asyncio
from app.services.graph.state import CostmateState
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.core.prompts import ELEMENT_DETECTOR_PROMPT
from app.core.logging import logger
from app.core.floor_utils import normalize_element

async def element_detector_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    image_paths = state.get("uploaded_page_paths", [])
    if not image_paths and state.get("uploaded_file_path"):
        image_paths = [state.get("uploaded_file_path")]
        
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: ELEMENT DETECTOR NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 📂 Input Pages: {len(image_paths)} image(s)")
    
    if not image_paths:
        raise ValueError(f"No image paths provided for element detector node in session {session_id}")

    try:
        schedule_registry = None
        if "intake_data" in state and isinstance(state["intake_data"], dict):
            schedule_registry = state["intake_data"].get("globalSettings", {}).get("scheduleRegistry")

        # Run on all pages in parallel
        async def process_page(path, idx):
            logger.info(f"  ├─ 🤖 [Page {idx+1}/{len(image_paths)}] Detecting structural elements...")
            
            prompt_to_use = ELEMENT_DETECTOR_PROMPT
            if schedule_registry:
                prompt_to_use = f"USER PROVIDED DOORS/WINDOWS SCHEDULE REGISTRY:\n{json.dumps(schedule_registry, indent=2)}\n\nUSE THIS REGISTRY AS THE SOURCE OF TRUTH FOR DOOR/WINDOW TYPES. EXTRACT THE LOCATIONS AND COUNTS OF THESE EXACT TYPES FROM THE FLOOR PLAN. DO NOT MAKE UP NEW TYPES.\n\n{ELEMENT_DETECTOR_PROMPT}"

            response_text = await openrouter_client.generate_chat(
                prompt=prompt_to_use,
                image_paths=[path],
                json_mode=True
            )
            parsed = parse_json_response(response_text)
            logger.info(f"  ├─ 🎉 [Page {idx+1}/{len(image_paths)}] Elements LLM parsed. Found "
                        f"{len(parsed.get('columns', []))} col scheds, "
                        f"{len(parsed.get('beams', []))} beam scheds, "
                        f"{len(parsed.get('doors', []))} door types, "
                        f"{len(parsed.get('windows', []))} window types.")
            return parsed
            
        results = []
        for idx, path in enumerate(image_paths):
            res = await process_page(path, idx)
            results.append(res)
        
        # Merge all elements
        merged_elements = {
            "doors": [],
            "windows": []
        }
        
        doors_by_type = {}
        windows_by_type = {}
        
        has_instance = schedule_registry and schedule_registry.get("instance_schedule")
        has_unit = schedule_registry and schedule_registry.get("unit_matrix", {}).get("present")
        
        if has_instance or has_unit:
            if has_instance:
                for inst in schedule_registry.get("instance_schedule", []):
                    dtype = str(inst.get("type")).strip().upper()
                    cat = str(inst.get("category", "door")).strip().lower()
                    if cat == "window":
                        if dtype not in windows_by_type:
                            windows_by_type[dtype] = {"type": dtype, "count": 0}
                        windows_by_type[dtype]["count"] += 1
                    else:
                        if dtype not in doors_by_type:
                            doors_by_type[dtype] = {"type": dtype, "count": 0}
                        doors_by_type[dtype]["count"] += 1
                        
            if has_unit:
                um = schedule_registry.get("unit_matrix", {})
                occ = um.get("occurrences_by_floor", {})
                dc = um.get("door_counts_per_unit_type", {})
                for unit, floors in occ.items():
                    try:
                        total_units = sum(int(c) for c in floors.values() if str(c).isdigit())
                    except:
                        total_units = 0
                    if unit in dc:
                        for dtype, count in dc[unit].items():
                            dtype = str(dtype).strip().upper()
                            try:
                                count = int(count)
                            except:
                                count = 1
                            if dtype not in doors_by_type:
                                doors_by_type[dtype] = {"type": dtype, "count": 0}
                            doors_by_type[dtype]["count"] += total_units * count
                            
            if schedule_registry and "type_registry" in schedule_registry:
                reg_doors = {str(d.get("type")).strip().upper(): d for d in schedule_registry["type_registry"].get("doors", [])}
                reg_windows = {str(w.get("type")).strip().upper(): w for w in schedule_registry["type_registry"].get("windows", [])}
                for dtype, d in doors_by_type.items():
                    if dtype in reg_doors:
                        rd = reg_doors[dtype]
                        d["width_m"] = rd.get("width_m", d.get("width_m"))
                        d["height_m"] = rd.get("height_m", d.get("height_m"))
                        d["material"] = rd.get("material", d.get("material"))
                        d["frame_type"] = rd.get("frame_type", d.get("frame_type"))
                for wtype, w in windows_by_type.items():
                    if wtype in reg_windows:
                        rw = reg_windows[wtype]
                        w["width_m"] = rw.get("width_m", w.get("width_m"))
                        w["height_m"] = rw.get("height_m", w.get("height_m"))
                        w["material"] = rw.get("material", w.get("material"))
        else:
            for elem in results:
                for d in elem.get("doors", []):
                    dtype = d.get("type", "D1").strip().upper()
                    if dtype not in doors_by_type:
                        doors_by_type[dtype] = d
                    else:
                        doors_by_type[dtype]["count"] = doors_by_type[dtype].get("count", 0) + d.get("count", 0)
                for w in elem.get("windows", []):
                    wtype = w.get("type", "W1").strip().upper()
                    if wtype not in windows_by_type:
                        windows_by_type[wtype] = w
                    else:
                        windows_by_type[wtype]["count"] = windows_by_type[wtype].get("count", 0) + w.get("count", 0)
                        
            if schedule_registry and "type_registry" in schedule_registry:
                reg_doors = {str(d.get("type")).strip().upper(): d for d in schedule_registry["type_registry"].get("doors", [])}
                reg_windows = {str(w.get("type")).strip().upper(): w for w in schedule_registry["type_registry"].get("windows", [])}
                for dtype, d in doors_by_type.items():
                    if dtype in reg_doors:
                        rd = reg_doors[dtype]
                        d["width_m"] = rd.get("width_m", d.get("width_m"))
                        d["height_m"] = rd.get("height_m", d.get("height_m"))
                        d["material"] = rd.get("material", d.get("material"))
                        d["frame_type"] = rd.get("frame_type", d.get("frame_type"))
                for wtype, w in windows_by_type.items():
                    if wtype in reg_windows:
                        rw = reg_windows[wtype]
                        w["width_m"] = rw.get("width_m", w.get("width_m"))
                        w["height_m"] = rw.get("height_m", w.get("height_m"))
                        w["material"] = rw.get("material", w.get("material"))
        
        # Always aggregate bounding boxes from visual results for trust/UI overlay
        for elem in results:
            for d in elem.get("doors", []):
                dtype = d.get("type", "UNKNOWN").strip().upper()
                bboxes = d.get("bounding_boxes", [])
                if bboxes:
                    if dtype not in doors_by_type:
                        doors_by_type[dtype] = {"type": dtype, "count": 0, "bounding_boxes": bboxes}
                    else:
                        doors_by_type[dtype]["bounding_boxes"] = doors_by_type[dtype].get("bounding_boxes", []) + bboxes
                        
            for w in elem.get("windows", []):
                wtype = w.get("type", "UNKNOWN").strip().upper()
                bboxes = w.get("bounding_boxes", [])
                if bboxes:
                    if wtype not in windows_by_type:
                        windows_by_type[wtype] = {"type": wtype, "count": 0, "bounding_boxes": bboxes}
                    else:
                        windows_by_type[wtype]["bounding_boxes"] = windows_by_type[wtype].get("bounding_boxes", []) + bboxes

        merged_elements["doors"] = list(doors_by_type.values())
        merged_elements["windows"] = list(windows_by_type.values())
        
        logger.info(f"----------------------------------------------------------------------\n"
                    f"✅ [{session_id}] COMPLETED: ELEMENT DETECTOR NODE\n"
                    f"  ├─ 🕒 Status: Success\n"
                    f"  ├─ 🚪 Total Doors Merged: {sum(d.get('count', 0) for d in merged_elements['doors'])} across {len(merged_elements['doors'])} type(s)\n"
                    f"  └─ 🪟 Total Windows Merged: {sum(w.get('count', 0) for w in merged_elements['windows'])} across {len(merged_elements['windows'])} type(s)\n"
                    f"======================================================================")
        return {
            "elements": merged_elements
        }
    except Exception as e:
        logger.error(f"  ❌ [{session_id}] Element Detector Node failed: {e}")
        logger.info(f"======================================================================")
        raise e

def get_mock_elements() -> dict:
    return {
        "elements": {
            "columns": [
                {"name": "C1", "dimensions_m": [0.23, 0.23], "count": 12, "shape": "rectangle"}
            ],
            "beams": [
                {"name": "PB1", "dimensions_m": [0.23, 0.45], "span_m": 5.44},
                {"name": "PB2", "dimensions_m": [0.23, 0.45], "span_m": 3.765}
            ],
            "doors": [
                {"type": "D1", "width_m": 0.9, "height_m": 2.1, "count": 18, "frame_material": "wood"},
                {"type": "D2", "width_m": 1.5, "height_m": 2.1, "count": 1, "frame_material": "aluminum"}
            ],
            "windows": [
                {"type": "W1", "width_m": 1.5, "height_m": 1.2, "count": 20, "has_grill": True}
            ],
            "staircases": [
                {"steps_count": 17, "rise_m": 0.15, "tread_m": 0.25, "waist_slab_thickness_m": 0.15}
            ]
        }
    }
