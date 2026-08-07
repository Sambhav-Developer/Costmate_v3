import os
import json
import asyncio
import traceback
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.services.graph.state import CostmateState
from app.core.logging import logger
from app.config import settings

# Common room keywords to filter out room name labels from door/window callouts
ROOM_KEYWORDS = {
    "room", "rm", "office", "toilet", "staff", "holding", "treatment", "bed", 
    "ex", "existing", "lounge", "lobby", "corridor", "hall", "stair", "storage", 
    "mech", "electrical", "elec", "janitor", "closet", "bath", "shower", "wc", 
    "vestibule", "entry", "exit", "classroom", "kitchen", "conf", "conference", 
    "shared", "hvac", "elevator", "utility", "laundry", "nourse", "care", "station"
}

def is_block_room_label(blocks, block_no, clean_mark) -> bool:
    if block_no < 0 or block_no >= len(blocks):
        return False
    try:
        b = blocks[block_no]
        block_text = b[4].lower()
        words = [w.strip(".,()[]{}-_#*") for w in block_text.split()]
        if len(words) > 1:
            if any(kw in words for kw in ROOM_KEYWORDS):
                return True
        return False
    except:
        return False

def normalize_opening_mode(val: str) -> str:
    val_clean = str(val).strip().upper()
    if val_clean in ["SINGLE", "SGL", "SINGLE-LEAF", "SINGLE LEAF", "1"]:
        return "SGL"
    if val_clean in ["DA", "DOUBLE ACTING", "DOUBLE-ACTING", "DOUBLE_ACTING"]:
        return "DA"
    if val_clean in ["CO", "DOUBLE-LEAF", "DOUBLE LEAF", "TWO-LEAF", "TWO LEAF", "2"]:
        return "CO"
    if val_clean in ["ELEV", "ELEVATOR"]:
        return "ELEV"
    if val_clean in ["FIXED", "CASEMENT"]:
        return val_clean
    return "SGL"


def _rects_overlap_x(r1, r2, tolerance=30.0):
    """Check if two rects share significant x-axis overlap (same column = same door)."""
    overlap = min(r1.x1, r2.x1) - max(r1.x0, r2.x0)
    span1 = r1.x1 - r1.x0
    span2 = r2.x1 - r2.x0
    min_span = min(span1, span2)
    if min_span < 1:
        return False
    return overlap / min_span > 0.5


def classify_opening_from_drawings(drawings_near, mark_rect, item: dict = None):
    """
    Classify a door's opening mode from nearby PDF path drawings and raw schedule facts.
    - CO:  cased opening / double-leaf (no door leaf in schedule, or 2+ distinct leaf arc groups)
    - DA:  double-acting / anti-barricade (indicated by schedule type/comments 'F AB'/'Anti-Barricade' or dashed stroke)
    - SGL: single-leaf (one solid swing arc)

    Returns: ("SGL" | "DA" | "CO")
    """
    import fitz as fz

    # 1. Rule 1: Check raw schedule facts FIRST.
    if item and isinstance(item, dict):
        mat = ""
        dtype = ""
        ftype = ""
        comments = ""
        for k, v in item.items():
            kl = str(k).lower().strip()
            val_str = str(v).strip().upper()
            if "material" in kl and "door" in kl:
                mat = val_str
            elif kl in ["door type", "type"]:
                dtype = val_str
            elif "frame type" in kl:
                ftype = val_str
            elif kl in ["comments", "remarks", "estimator notes", "description"]:
                comments = val_str

        # Check for Cased Opening (CO) in schedule (no door panel)
        if mat in ["-", "", "NONE", "N/A", "CASED OPENING"] and dtype in ["-", "", "CO", "NONE", "N/A", "CASED OPENING", "CASED"]:
            logger.info(f"CV Drawing Analysis: Schedule indicates Cased Opening for mark (mat={mat!r}, type={dtype!r}) -> CO")
            return "CO"
        if dtype in ["CO", "CASED OPENING", "CASED"]:
            logger.info(f"CV Drawing Analysis: Schedule indicates Cased Opening type for mark -> CO")
            return "CO"

        # Check for Double-Acting (DA) / Anti-Barricade in schedule
        da_tokens = ["AB", "DA", "DOUBLE ACTING", "DOUBLE-ACTING", "ANTI-BARRICADE", "ANTI - BARRICADE"]
        dtype_tokens = dtype.split()
        if any(t in dtype_tokens for t in ["AB", "DA"]) or any(t in dtype for t in ["DOUBLE ACTING", "ANTI-BARRICADE", "ANTI - BARRICADE"]):
            logger.info(f"CV Drawing Analysis: Schedule indicates Anti-Barricade / Double-Acting (type={dtype!r}) -> DA")
            return "DA"
        if any(t in ftype for t in ["AB", "DA"]) or any(t in comments for t in ["ANTI-BARRICADE", "ANTI - BARRICADE", "DOUBLE ACTING", "DOUBLE-ACTING"]):
            logger.info(f"CV Drawing Analysis: Schedule comments/frame indicate Anti-Barricade / Double-Acting -> DA")
            return "DA"

    mark_cx = (mark_rect.x0 + mark_rect.x1) / 2
    mark_cy = (mark_rect.y0 + mark_rect.y1) / 2

    # 2. Rule 2: Check for Double-Acting (DA) dashed path strokes near the mark (ignoring label bubbles)
    for d in drawings_near:
        d_rect = fz.Rect(d.get("rect"))
        cx = (d_rect.x0 + d_rect.x1) / 2
        cy = (d_rect.y0 + d_rect.y1) / 2
        dist = ((cx - mark_cx) ** 2 + (cy - mark_cy) ** 2) ** 0.5
        area = d_rect.width * d_rect.height

        # Skip mark label bubble annotation strokes
        if dist < 15 and area < 200:
            continue

        if dist < 65:
            dashes = d.get("dashes", None)
            is_dashed = False
            if dashes is not None:
                if isinstance(dashes, str):
                    clean = dashes.strip()
                    if clean and clean not in ("[] 0", "[] 0.0", "[]", ""):
                        is_dashed = True
                elif isinstance(dashes, (list, tuple)) and len(dashes) > 0:
                    is_dashed = True

            if is_dashed:
                logger.info(f"CV Drawing Analysis: Found dashed stroke path near mark (dist={dist:.1f}) -> DA")
                return "DA"

    # 3. Rule 3: Collect arc curves for single vs double leaf counting (tight 65pt radius)
    arc_paths = []
    for d in drawings_near:
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if not has_curve:
            continue

        arc_rect = fz.Rect(d.get("rect"))
        arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
        arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
        dist = ((arc_cx - mark_cx) ** 2 + (arc_cy - mark_cy) ** 2) ** 0.5

        if dist > 65:
            continue

        # Skip tiny mark-label annotation bubble arcs
        arc_area = arc_rect.width * arc_rect.height
        if dist < 15 and arc_area < 200:
            continue

        arc_paths.append({"rect": arc_rect, "cx": arc_cx, "cy": arc_cy, "dist": dist})

    if not arc_paths:
        return "SGL"

    def centroid_dist(a, b):
        return ((a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2) ** 0.5

    groups = []
    for arc in arc_paths:
        placed = False
        for g in groups:
            if any(centroid_dist(arc, existing) < 45 for existing in g):
                g.append(arc)
                placed = True
                break
        if not placed:
            groups.append([arc])

    distinct_leaves = len(groups)
    logger.info(f"CV Drawing Analysis: {distinct_leaves} distinct door leaf group(s) -> {'CO' if distinct_leaves >= 2 else 'SGL'}")

    if distinct_leaves >= 2:
        return "CO"
    return "SGL"


async def get_location_from_crop(crop_path: str, mark: str, floor_no: int, semaphore: asyncio.Semaphore) -> str:
    """
    Use LLM vision ONLY for room name detection (location).
    Opening mode is classified programmatically from PDF drawing paths and schedule facts.
    """
    if not crop_path or not os.path.exists(crop_path):
        return "", "Interior"
    async with semaphore:
        prompt = f"""
        Look at this cropped image from a floor plan around the door/window mark '{mark}' on Floor {floor_no}.

        Identify the name of the room or corridor where this door/window is located, using room labels printed in or near the space (e.g. "Shared Office", "Secure Holding", "Toilet", "Staff Lounge").

        IMPORTANT RULES FOR CLASSIFICATION:
        - "EX." or "EX " prefixed to a room label means "EXISTING" (a room that already exists in the building), NOT "Exterior". Example: "EX. NON-ADA STAFF TOILET" -> location is "Non-ADA Staff Toilet (Existing)", and this tells you nothing about int_ext by itself.
        - Set "int_ext" to "Interior" by default. Only set it to "Exterior" if the space is clearly outdoors or open-air — e.g. labeled "Roof", "Courtyard", "Patio", "Areaway", or the door/window opens directly onto an exterior wall with no enclosed room beyond it.
        - If the room label is unclear, cut off, or not visible in the crop, set "location" to "Unknown" rather than guessing a room name.

        Return ONLY a raw JSON block, no markdown fences, no explanation:
        {{
            "location": "room_name",
            "int_ext": "Interior/Exterior"
        }}
        """
        try:
            res = await openrouter_client.generate_chat(prompt=prompt, image_paths=[crop_path], json_mode=True, temperature=0.1)
            data = parse_json_response(res)
            location = data.get("location", "")
            int_ext = data.get("int_ext", "Interior")

            # Post-processing override: prevent false "Exterior" when room label has EX. (Existing) or interior keywords
            loc_upper = location.upper()
            if int_ext == "Exterior":
                interior_kws = [
                    "TOILET", "OFFICE", "HOLDING", "ROOM", "CORRIDOR", "STAIR", "EX.", "EXISTING",
                    "CLOSET", "HALL", "LOUNGE", "JANITOR", "EVS", "ELEC", "MECH", "UTILITY",
                    "STORE", "STORAGE", "ENTRY", "VESTIBULE", "RECEPTION", "TRIAGE", "WAITING",
                    "CONSULT", "NURSE", "LINEN", "TRASH", "PASSAGEWAY", "STATION", "LAB"
                ]
                if any(kw in loc_upper for kw in interior_kws):
                    int_ext = "Interior"

            return location, int_ext
        except Exception as e:
            logger.error(f"Error getting location for mark {mark} on Floor {floor_no}: {e}")
            return "", "Interior"


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

async def cv_detector_node(state: CostmateState) -> dict:
    logger.info("CV Detector: Starting crop-based door & window analysis node...")
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed. Cannot run crop analysis.")
        return {"cv_results": {"detections": []}}

    # Gather all raw drawing paths/URLs
    raw_drawings = []
    intake = state.get("intake_data") or {}
    floors = intake.get("floors", [])
    logger.info(f"CV Detector DEBUG: intake floors count={len(floors) if floors else 0}")
    if isinstance(floors, list):
        for i, floor in enumerate(floors):
            raw_url = floor.get("rawUrl")
            page_urls = floor.get("pageUrls", [])
            logger.info(f"CV Detector DEBUG: floor[{i}] rawUrl={raw_url!r}, pageUrls count={len(page_urls)}")
            if raw_url and raw_url not in raw_drawings:
                raw_drawings.append(raw_url)
                
    if not raw_drawings:
        overall_file = state.get("uploaded_file_path")
        logger.info(f"CV Detector DEBUG: No rawUrls found in floors. Fallback uploaded_file_path={overall_file!r}")
        if overall_file:
            raw_drawings.append(overall_file)
            
    logger.info(f"CV Detector DEBUG: raw_drawings to process: {raw_drawings}")
    if not raw_drawings:
        logger.warning("No floor plan drawings found to analyze.")
        return {"cv_results": {"detections": []}}
        
    # Get master schedule items to know which marks to look for
    qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
    doors = qa.get("doors") or []
    windows = qa.get("windows") or []
    items = doors + windows
    
    if not items:
        # Fall back to parsed schedule data from schedule_parser_node
        items = state.get("schedule_data") or []
        
    logger.info(f"CV Detector DEBUG: total schedule items={len(items)}")
    if items:
        sample = items[:3]
        for s in sample:
            logger.info(f"CV Detector DEBUG: sample item keys={list(s.keys())}, extracted_mark={get_item_mark(s)!r}")
    if not items:
        logger.warning("No schedule items found in state to locate.")
        return {"cv_results": {"detections": []}}

    sched_marks = set()
    sched_items_by_mark = {}
    for item in items:
        mark_val = get_item_mark(item)
        if mark_val:
            sched_marks.add(mark_val)
            if mark_val not in sched_items_by_mark:
                sched_items_by_mark[mark_val] = item

    downloaded_temps = []
    location_tasks = []    # (mark, floor_no, crop_path) for LLM location extraction
    all_temp_crops = []
    detections = []        # results from programmatic opening mode classification
    
    # Global concurrency semaphore for LLM vision crops
    semaphore = asyncio.Semaphore(8)
    
    try:
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
        for idx, file_source in enumerate(raw_drawings):
            temp_local_file = None
            local_raw_path = None
            floor_no = idx + 1
            
            # Download the file if it's hosted in the cloud (Cloudinary URL)
            if file_source.startswith("http://") or file_source.startswith("https://"):
                try:
                    import urllib.request
                    _, ext = os.path.splitext(file_source.split('?')[0])
                    ext = ext.lower()
                    if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
                        ext = ".pdf"
                        
                    temp_local_file = os.path.join(settings.OUTPUT_DIR, f"temp_cv_{idx}_{state.get('session_id', 'temp')}{ext}")
                    logger.info(f"Downloading CV drawing {idx}: {file_source} -> {temp_local_file}")
                    
                    req = urllib.request.Request(file_source, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response, open(temp_local_file, 'wb') as out_file:
                        out_file.write(response.read())
                    local_raw_path = temp_local_file
                    downloaded_temps.append(temp_local_file)
                except Exception as dl_err:
                    logger.error(f"Failed to download drawing {idx}: {dl_err}")
                    continue
            else:
                local_raw_path = file_source
                if not os.path.exists(local_raw_path):
                    logger.warning(f"Local drawing path does not exist: {local_raw_path}")
                    continue
                    
            # Open/Convert to PDF
            try:
                file_ext = os.path.splitext(local_raw_path)[1].lower()
                if file_ext in [".png", ".jpg", ".jpeg"]:
                    img_doc = fitz.open(local_raw_path)
                    pdf_bytes = img_doc.convert_to_pdf()
                    doc = fitz.open("pdf", pdf_bytes)
                    img_doc.close()
                else:
                    doc = fitz.open(local_raw_path)
            except Exception as open_err:
                logger.error(f"Failed to open drawing {local_raw_path}: {open_err}")
                continue
                
            # Scan pages for schedule marks
            for page_idx, page in enumerate(doc):
                blocks = page.get_text("blocks")
                words_on_page = page.get_text("words")
                drawings_on_page = page.get_drawings()
                logger.info(f"CV Detector DEBUG: floor[{idx}] page[{page_idx}] has {len(words_on_page)} words, {len(drawings_on_page)} drawing paths, looking for {len(sched_marks)} marks")
                
                word_indices = {}
                page_matched_positions = []  # Deduplicate nearby matches for same mark on page
                
                for w in words_on_page:
                    word_text = w[4].strip(".,()[]{}-_#*").upper()
                    
                    if word_text in sched_marks:
                        w_x, w_y = w[0], w[1]
                        
                        # Deduplicate: skip if this exact mark text was matched within 30pt on this page
                        if any(p_text == word_text and abs(p_x - w_x) < 30 and abs(p_y - w_y) < 30 for p_text, p_x, p_y in page_matched_positions):
                            logger.info(f"CV Detector: Skipping duplicate match for {word_text} at ({w_x:.1f},{w_y:.1f})")
                            continue
                        page_matched_positions.append((word_text, w_x, w_y))

                        logger.info(f"CV Detector DEBUG: MATCH FOUND word={word_text!r} at ({w[0]:.1f},{w[1]:.1f})")
                        # Skip room label blocks
                        block_no = w[5]
                        if is_block_room_label(blocks, block_no, word_text):
                            logger.info(f"CV Detector DEBUG: Skipping {word_text!r} - room label")
                            continue
                            
                        # Increment index of this word on the page for unique crop filename
                        word_indices[word_text] = word_indices.get(word_text, 0) + 1
                        w_idx = word_indices[word_text]
                        
                        # Bounding box of the mark word
                        import fitz as fz
                        inst_rect = fz.Rect(w[0], w[1], w[2], w[3])
                        
                        # Search for PDF drawing paths near this mark (70pt radius)
                        # Prevents neighboring doors' arcs from bleeding into nearby marks
                        search_rect = inst_rect + (-70, -70, 70, 70)
                        nearby_drawings = [
                            d for d in drawings_on_page
                            if d.get("rect") and fz.Rect(d["rect"]).intersects(search_rect)
                        ]
                        
                        # Programmatic opening mode classification from PDF path data + schedule facts
                        sched_item = sched_items_by_mark.get(word_text)
                        opening_mode = classify_opening_from_drawings(nearby_drawings, inst_rect, item=sched_item)
                        logger.info(f"CV Detector: Mark {word_text} programmatic opening mode = {opening_mode}")
                        
                        # Generate crop image for LLM location/room name detection only
                        clip_rect = inst_rect + (-80, -80, 80, 80)
                        try:
                            pix = page.get_pixmap(clip=clip_rect, dpi=200)
                            import re, uuid
                            clean_mark_file = re.sub(r'[^a-zA-Z0-9_-]', '_', word_text)
                            crop_filename = f"crop_f{floor_no}_p{page_idx}_{clean_mark_file}_{w_idx}_{uuid.uuid4().hex[:6]}.png"
                            crop_path = os.path.join(settings.OUTPUT_DIR, crop_filename)
                            pix.save(crop_path)
                            all_temp_crops.append(crop_path)
                            
                            # Queue LLM task for location/room name only
                            location_tasks.append((word_text, floor_no, crop_path, opening_mode))
                        except Exception as crop_err:
                            logger.error(f"Failed to create crop for mark {word_text}: {crop_err}")
                            # Still record the programmatic result without location
                            detections.append({
                                "mark": word_text,
                                "location": "",
                                "opening_mode": opening_mode,
                                "int_ext": "Interior",
                                "floor_no": str(floor_no)
                            })
                            
            doc.close()

        # Run location LLM tasks concurrently
        logger.info(f"CV Detector: Running {len(location_tasks)} location-detection LLM tasks...")
        
        async def run_location_task(mark, floor_no, crop_path, opening_mode):
            location, int_ext = await get_location_from_crop(crop_path, mark, floor_no, semaphore)
            return {
                "mark": mark,
                "location": location,
                "opening_mode": opening_mode,  # programmatically determined
                "int_ext": int_ext,
                "floor_no": str(floor_no)
            }
        
        location_results = await asyncio.gather(
            *[run_location_task(m, f, cp, om) for m, f, cp, om in location_tasks]
        )
        detections.extend(location_results)
        
        # Cleanup temporary raw downloads
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
                
        # Cleanup temporary crop images
        for crop_file in all_temp_crops:
            if os.path.exists(crop_file):
                try: os.remove(crop_file)
                except: pass
                
        logger.info(f"CV Detector: Completed. Found and classified {len(detections)} marks on drawings.")
        return {"cv_results": {"detections": detections}}
        
    except Exception as e:
        logger.error(f"CV Detector overall failure: {e}")
        traceback.print_exc()
        # Clean up all temp files
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
        for crop_file in all_temp_crops:
            if os.path.exists(crop_file):
                try: os.remove(crop_file)
                except: pass
        return {"cv_results": {"detections": []}}
