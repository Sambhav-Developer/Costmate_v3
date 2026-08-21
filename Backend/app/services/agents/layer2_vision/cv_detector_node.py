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
    "shared", "hvac", "elevator", "utility", "laundry", "nourse", "care", "station",
    "exam", "examination", "it", "pantry", "waiting", "reception", "soiled", "clean", 
    "nurse", "nook", "dictation", "physician", "touchdown", "med", "meds", "unisex", 
    "vest", "clos", "lrd", "sub", "wait", "consult", "consultation", "work", "lockers", 
    "triage", "harrison", "mamaroneck"
}

def reassemble_pdf_words(words):
    if not words:
        return []
    sorted_words = sorted(words, key=lambda x: (x[5], x[6], x[0]))
    merged = []
    i = 0
    n = len(sorted_words)
    while i < n:
        w = list(sorted_words[i])
        while i + 1 < n:
            next_w = sorted_words[i + 1]
            if next_w[5] == w[5] and next_w[6] == w[6]:
                gap = next_w[0] - w[2]
                if 0 <= gap < 8:
                    w[4] = w[4] + next_w[4]
                    w[2] = next_w[2]
                    w[3] = max(w[3], next_w[3])
                    i += 1
                    continue
            break
        merged.append(tuple(w))
        i += 1
    return merged

def find_closest_schedule_mark(word_text, sched_marks):
    if word_text in sched_marks:
        return word_text
    # Common OCR digit-to-letter confusion fixes
    normalized_variants = []
    # Variant A: replace all '0' and 'O' with 'C' (for 3C03/3C06A type marks read as 3003/3O03)
    v_c = word_text.replace('0', 'C').replace('O', 'C')
    normalized_variants.append(v_c)
    # Variant B: replace 'C' with '0'
    v_0 = word_text.replace('C', '0')
    normalized_variants.append(v_0)
    # Variant C: replace 'O' with '0'
    v_o2 = word_text.replace('O', '0')
    normalized_variants.append(v_o2)
    # Variant D: replace '8' with 'B' or 'B' with '8'
    normalized_variants.append(word_text.replace('8', 'B'))
    normalized_variants.append(word_text.replace('B', '8'))
    
    for v in normalized_variants:
        if v != word_text and v in sched_marks:
            return v
    return None

def get_schedule_table_rects(page):
    import fitz
    rects = []
    for term in ["DOOR AND FRAME SCHEDULE", "DOOR SCHEDULE", "WINDOW SCHEDULE", "FRAME SCHEDULE"]:
        rects_found = page.search_for(term)
        for r in rects_found:
            page_rect = page.rect
            table_rect = fitz.Rect(r.x0 - 20, r.y0 - 50, page_rect.x1, page_rect.y1)
            rects.append(table_rect)
    return rects

def is_block_room_label(blocks, block_no, clean_mark) -> bool:
    if block_no < 0 or block_no >= len(blocks):
        return False
    try:
        b = blocks[block_no]
        block_text = b[4].strip().upper()
        block_words = [w.strip(".,()[]{}-_#*") for w in block_text.split()]
        block_words = [w for w in block_words if w]
        
        words_lower = [w.lower() for w in block_words]
        if any(kw in words_lower for kw in ROOM_KEYWORDS):
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
    if val_clean in ["PR", "PAIR", "PAIRED", "DOUBLE SGL", "PR.", "PRS", "P"]:
        return "PR"
    if val_clean in ["CO", "DOUBLE-LEAF", "DOUBLE LEAF", "TWO-LEAF", "TWO LEAF", "2", "CASED", "CASED OPENING"]:
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
        w_a = ""
        w_b = ""
        frame_mat = ""
        for k, v in item.items():
            kl = str(k).lower().strip()
            val_str = str(v).strip().upper()
            if "material" in kl and "door" in kl:
                mat = val_str
            elif "material" in kl and "frame" in kl:
                frame_mat = val_str
            elif "material" in kl and not mat:
                mat = val_str
            elif kl in ["door type", "type"]:
                dtype = val_str
            elif "frame type" in kl:
                ftype = val_str
            elif kl in ["comments", "remarks", "estimator notes", "description"]:
                comments = val_str
            elif kl in ["width a", "width_a", "w_a", "wa"]:
                w_a = str(v).strip()
            elif kl in ["width b", "width_b", "w_b", "wb"]:
                w_b = str(v).strip()

        # Check for Storefront / Aluminum & Glass Opening
        storefront_tokens = ["AL", "ALUM", "ALUMINUM", "GLASS", "GL", "STOREFRONT"]
        if mat in storefront_tokens or frame_mat in storefront_tokens or any(tok in comments for tok in ["STOREFRONT", "AD SYSTEM", "ALUMINUM"]):
            logger.info(f"CV Drawing Analysis: Schedule indicates Storefront / Aluminum Entry (mat={mat!r}, frame_mat={frame_mat!r}) -> STOREFRONT")
            return "STOREFRONT"

        # If both Width A and Width B are populated in the schedule, it is a Pair door (PR)
        if w_a and w_b and w_a not in ["-", ""] and w_b not in ["-", ""]:
            logger.info(f"CV Drawing Analysis: Schedule indicates both Width A ({w_a!r}) and Width B ({w_b!r}) -> PR")
            return "PR"
        # If Width A is populated and Width B is empty/dash, it is a single-leaf door (SGL)
        if w_a and w_a not in ["-", ""] and (not w_b or w_b in ["-", ""]):
            logger.info(f"CV Drawing Analysis: Schedule indicates single Width A -> SGL")
            return "SGL"

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
        comments_upper = comments.upper()
        if any(t in comments_upper for t in ["DBL ACT", "DA", "DOUBLE ACTING", "DOUBLE-ACTING", "ANTI-BARRICADE", "ANTI - BARRICADE", "AB"]):
            logger.info(f"CV Drawing Analysis: Schedule comments indicate Anti-Barricade / Double-Acting -> DA")
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
                # To distinguish dashed walls from dashed swings, ensure it's not a long straight wall line
                is_straight_long = False
                items = d.get("items", [])
                has_curves = any(it[0] in ("c", "qu") for it in items)
                
                # If it's a straight segment and has a large span, it's a wall line, not a door swing
                if not has_curves and (d_rect.width > 80 or d_rect.height > 80):
                    is_straight_long = True
                    
                if not is_straight_long:
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

        if dist > 50:
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
    logger.info(f"CV Drawing Analysis: {distinct_leaves} distinct door leaf group(s) -> {'PR' if distinct_leaves >= 2 else 'SGL'}")

    if distinct_leaves >= 2:
        return "PR"
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
        Look at this cropped floor plan image around the door/window mark '{mark}' on Floor {floor_no}.

        CRITICAL: The specific door/window mark being analyzed is highlighted by the BRIGHT RED TARGET ARROW AND RED CIRCLE drawn on the image.

        Identify the name of the room or corridor where THIS specific door/window is located, using room labels printed in or near the space (e.g. "Shared Office", "Secure Holding", "Toilet", "Staff Lounge", "Command Center", "Stair C").

        IMPORTANT RULES FOR CLASSIFICATION:
        - "EX." or "EX " prefixed to a room label means "EXISTING" (a room that already exists in the building), NOT "Exterior". Example: "EX. NON-ADA STAFF TOILET" -> location is "Non-ADA Staff Toilet (Existing)", and this tells you nothing about int_ext by itself.
        - Set "int_ext" to "Interior" by default. Only set it to "Exterior" if the space is clearly outdoors or open-air — e.g. labeled "Roof", "Courtyard", "Patio", "Areaway", or the door/window opens directly onto an exterior wall with no enclosed room beyond it.
        - Focus strictly on the room connected to the door pointed to by the RED ARROW. Do NOT return the label of an adjacent room that belongs to a different door.
        - If the room label for this door is unclear, cut off, or not visible in the crop, set "location" to "Unknown" rather than guessing a room name.

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

def run_opencv_geometric_detection(page, floor_no, page_idx, sched_marks, temp_dir):
    """
    Use OpenCV locally to detect circular, hexagonal, and rectangular callout tags.
    Returns a list of fitz.Rect regions in PDF points coords.
    """
    import cv2
    import numpy as np
    import re
    import uuid
    import fitz as fz
    
    # Render page to high-res PNG for OpenCV
    scale = 2.0  # 2x zoom for high-res details
    mat = fz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    page_img_path = os.path.join(temp_dir, f"page_full_f{floor_no}_p{page_idx}.png")
    pix.save(page_img_path)
    
    img = cv2.imread(page_img_path)
    if img is None:
        return []
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    height, width = img.shape[:2]
    page_width = page.rect.width
    page_height = page.rect.height
    
    candidates = []
    detected_boxes = []
    
    def is_duplicate(ymin, xmin, ymax, xmax):
        for box in detected_boxes:
            cy1 = (ymin + ymax) / 2
            cx1 = (xmin + xmax) / 2
            cy2 = (box[0] + box[2]) / 2
            cx2 = (box[1] + box[3]) / 2
            dist = ((cy1 - cy2)**2 + (cx1 - cx2)**2)**0.5
            if dist < 0.03: # 3% of page dimension
                return True
        return False
        
    # Track A: Hough Circles (Circular tags)
    circles = cv2.HoughCircles(
        blurred, 
        cv2.HOUGH_GRADIENT, 
        dp=1.2, 
        minDist=40, 
        param1=50, 
        param2=35, 
        minRadius=15, 
        maxRadius=65
    )
    
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        for (x, y, r) in circles:
            px_ymin = max(0, y - r - 8)
            px_xmin = max(0, x - r - 8)
            px_ymax = min(height, y + r + 8)
            px_xmax = min(width, x + r + 8)
            
            ymin = px_ymin / scale
            xmin = px_xmin / scale
            ymax = px_ymax / scale
            xmax = px_xmax / scale
            
            if not is_duplicate(ymin/page_height, xmin/page_width, ymax/page_height, xmax/page_width):
                detected_boxes.append((ymin/page_height, xmin/page_width, ymax/page_height, xmax/page_width))
                candidates.append(fz.Rect(xmin, ymin, xmax, ymax))
                
    # Track B: Contours (Hexagonal / Rectangular tags)
    _, thresh = cv2.threshold(blurred, 150, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for c in contours:
        area = cv2.contourArea(c)
        if 800 <= area <= 15000:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            if len(approx) in [4, 5, 6, 8]:
                x, y, w, h = cv2.boundingRect(c)
                aspect_ratio = float(w)/h
                if 0.7 <= aspect_ratio <= 1.4:
                    px_ymin = max(0, y - 8)
                    px_xmin = max(0, x - 8)
                    px_ymax = min(height, y + h + 8)
                    px_xmax = min(width, x + w + 8)
                    
                    ymin = px_ymin / scale
                    xmin = px_xmin / scale
                    ymax = px_ymax / scale
                    xmax = px_xmax / scale
                    
                    if not is_duplicate(ymin/page_height, xmin/page_width, ymax/page_height, xmax/page_width):
                        detected_boxes.append((ymin/page_height, xmin/page_width, ymax/page_height, xmax/page_width))
                        candidates.append(fz.Rect(xmin, ymin, xmax, ymax))
                        
    try: os.remove(page_img_path)
    except: pass
    
    return candidates

async def extract_mark_from_tag_crop(crop_path: str, sched_marks: set, semaphore: asyncio.Semaphore) -> str:
    """
    Call VLM on a tight OpenCV-detected geometric crop to identify the door/window mark.
    """
    if not crop_path or not os.path.exists(crop_path):
        return "NONE"
    async with semaphore:
        prompt = f"""
        Identify the door or window mark (e.g. 3C03, D-1, W-2, RS012, or similar) printed inside this circle/box.
        Select from this list of known project marks if there is a match: {sorted(list(sched_marks))}.
        If no valid mark from this list is printed in the crop, return 'NONE'.
        Return ONLY the matched mark string or 'NONE'. No other explanation, no markdown.
        """
        try:
            res = await openrouter_client.generate_chat(prompt=prompt, image_paths=[crop_path], json_mode=True, temperature=0.1)
            text = str(res).strip().upper()
            if "{" in text:
                data = parse_json_response(res)
                text = str(data.get("mark", data.get("text", "NONE"))).strip().upper()
            
            for sm in sched_marks:
                if sm == text or sm in text or text in sm:
                    return sm
            return "NONE"
        except Exception as e:
            logger.error(f"Failed to read mark from tag crop: {e}")
            return "NONE"

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

    # Build drawing/page to floor_name map
    drawing_floor_map = {}
    if isinstance(floors, list):
        for i, floor in enumerate(floors):
            fname = floor.get("name") or f"Level {i+1}"
            raw_url = floor.get("rawUrl")
            page_urls = floor.get("pageUrls", [])
            if raw_url:
                drawing_floor_map[raw_url] = fname
            for p_url in page_urls:
                drawing_floor_map[p_url] = fname
            drawing_floor_map[i] = fname

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
                effective_floor_idx = page_idx if len(raw_drawings) == 1 and len(doc) > 1 else idx
                floor_name = (
                    drawing_floor_map.get(file_source) or 
                    drawing_floor_map.get(effective_floor_idx) or 
                    (floors[effective_floor_idx].get("name") if (isinstance(floors, list) and effective_floor_idx < len(floors) and floors[effective_floor_idx].get("name")) else None) or 
                    f"Level {effective_floor_idx + 1}"
                )
                floor_no = effective_floor_idx + 1
                blocks = page.get_text("blocks")
                words_on_page = reassemble_pdf_words(page.get_text("words"))
                drawings_on_page = page.get_drawings()
                logger.info(f"CV Detector DEBUG: floor[{idx}] page[{page_idx}] has {len(words_on_page)} words, {len(drawings_on_page)} drawing paths, looking for {len(sched_marks)} marks")
                
                word_indices = {}
                table_rects = get_schedule_table_rects(page)
                
                # --- SCANNED / RASTER DRAWING FALLBACK (OPENCV SEARCH) ---
                if len(words_on_page) < 5:
                    logger.info("CV Detector: Scanned/Raster drawing detected. Running OpenCV shape detection fallback...")
                    tag_rects = run_opencv_geometric_detection(page, floor_no, page_idx, sched_marks, settings.OUTPUT_DIR)
                    logger.info(f"CV Detector: OpenCV found {len(tag_rects)} candidate tags on page. Querying VLM for OCR...")
                    
                    for tag_idx, tr in enumerate(tag_rects):
                        try:
                            pix = page.get_pixmap(clip=tr, dpi=200)
                            import uuid, fitz as fz
                            crop_filename = f"opencv_crop_f{floor_no}_p{page_idx}_{tag_idx}_{uuid.uuid4().hex[:6]}.png"
                            crop_path = os.path.join(settings.OUTPUT_DIR, crop_filename)
                            pix.save(crop_path)
                            all_temp_crops.append(crop_path)
                            
                            detected_mark = await extract_mark_from_tag_crop(crop_path, sched_marks, semaphore)
                            if detected_mark != "NONE":
                                logger.info(f"CV Detector: OpenCV + VLM matched mark {detected_mark} at crop {tag_idx}")
                                
                                # Draw Target Pin on Crop
                                from PIL import Image, ImageDraw
                                try:
                                    img = Image.open(crop_path).convert("RGB")
                                    draw = ImageDraw.Draw(img)
                                    cx = img.width / 2
                                    cy = img.height / 2
                                    draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], outline=(255, 0, 0), width=4)
                                    img.save(crop_path)
                                except Exception as pin_err:
                                    logger.warning(f"Failed to draw target on OpenCV crop: {pin_err}")
                                
                                # Classify opening mode programmatically
                                search_rect = tr + (-60, -60, 60, 60)
                                nearby_drawings = [
                                    d for d in drawings_on_page
                                    if d.get("rect") and fz.Rect(d["rect"]).intersects(search_rect)
                                ]
                                sched_item = sched_items_by_mark.get(detected_mark)
                                opening_mode = classify_opening_from_drawings(nearby_drawings, tr, item=sched_item)
                                
                                location_tasks.append((detected_mark, floor_no, floor_name, crop_path, opening_mode))
                        except Exception as tag_err:
                            logger.error(f"Error processing OpenCV tag crop {tag_idx}: {tag_err}")
                    continue
                
                # 1. Collect candidates by mark (Vector text track)
                candidates_by_mark = {}
                for w in words_on_page:
                    raw_word = w[4].strip(".,()[]{}-_#*").upper()
                    
                    matched_mark = find_closest_schedule_mark(raw_word, sched_marks)
                    if matched_mark:
                        word_text = matched_mark
                        w_x, w_y = w[0], w[1]
                        w_cx = (w[0] + w[2]) / 2
                        w_cy = (w[1] + w[3]) / 2
                        
                        # Skip if the match falls inside a masked schedule table area
                        is_inside_table = False
                        for tr in table_rects:
                            if w_cx >= tr.x0 and w_cx <= tr.x1 and w_cy >= tr.y0 and w_cy <= tr.y1:
                                is_inside_table = True
                                break
                        if is_inside_table:
                            continue
                            
                        # Skip if block is room label block
                        block_no = w[5]
                        if is_block_room_label(blocks, block_no, word_text):
                            logger.info(f"CV Detector: Skipping block {block_no} for mark {word_text} (room label keyword)")
                            continue
                            
                        import fitz as fz
                        inst_rect = fz.Rect(w[0], w[1], w[2], w[3])
                        search_rect = inst_rect + (-70, -70, 70, 70)
                        nearby_drawings = [
                            d for d in drawings_on_page
                            if d.get("rect") and fz.Rect(d["rect"]).intersects(search_rect)
                        ]
                        
                        # Count nearby arc curves
                        arc_paths = []
                        for d in nearby_drawings:
                            items = d.get("items", [])
                            has_curve = any(it[0] in ("c", "qu") for it in items)
                            if not has_curve:
                                continue
                            arc_rect = fz.Rect(d.get("rect"))
                            arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
                            arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
                            dist = ((arc_cx - w_cx) ** 2 + (arc_cy - w_cy) ** 2) ** 0.5
                            if dist <= 50:
                                # Skip tiny label circle arcs
                                arc_area = arc_rect.width * arc_rect.height
                                if dist < 15 and arc_area < 200:
                                    continue
                                arc_paths.append(d)
                                
                        candidates_by_mark.setdefault(word_text, []).append({
                            "word": w,
                            "w_x": w_x,
                            "w_y": w_y,
                            "w_cx": w_cx,
                            "w_cy": w_cy,
                            "inst_rect": inst_rect,
                            "nearby_drawings": nearby_drawings,
                            "arc_count": len(arc_paths)
                        })
                        
                for word_text, matches in candidates_by_mark.items():
                    # Sort matches by arc count descending so those with door arcs are prioritized
                    sorted_matches = sorted(matches, key=lambda x: x["arc_count"], reverse=True)
                        
                    # Also apply simple spatial deduplication: within 60pt
                    final_matches = []
                    for m in sorted_matches:
                        if any(abs(fm["w_cx"] - m["w_cx"]) < 60 and abs(fm["w_cy"] - m["w_cy"]) < 60 for fm in final_matches):
                            continue
                        final_matches.append(m)
                        
                    for m in final_matches:
                        w = m["word"]
                        w_x, w_y = m["w_x"], m["w_y"]
                        w_cx, w_cy = m["w_cx"], m["w_cy"]
                        inst_rect = m["inst_rect"]
                        nearby_drawings = m["nearby_drawings"]
                        
                        logger.info(f"CV Detector DEBUG: MATCH FOUND word={word_text!r} at ({w_cx:.1f},{w_cy:.1f})")
                        
                        # Increment index of this word on the page for unique crop filename
                        word_indices[word_text] = word_indices.get(word_text, 0) + 1
                        w_idx = word_indices[word_text]
                        
                        # Bounding box & center of the mark word
                        import fitz as fz
                        mark_cx = w_cx
                        mark_cy = w_cy
                        
                        # Programmatic opening mode classification
                        sched_item = sched_items_by_mark.get(word_text)
                        opening_mode = classify_opening_from_drawings(nearby_drawings, inst_rect, item=sched_item)
                        logger.info(f"CV Detector: Mark {word_text} programmatic opening mode = {opening_mode}")
                        
                        # Solution 1: Expand crop radius to 140pt to capture room labels in large rooms,
                        # and draw a BRIGHT RED TARGET ARROW & CIRCLE pointing directly at (mark_cx, mark_cy)
                        clip_rect = inst_rect + (-140, -140, 140, 140)
                        try:
                            pix = page.get_pixmap(clip=clip_rect, dpi=200)
                            import re, uuid
                            from PIL import Image, ImageDraw
                            
                            clean_mark_file = re.sub(r'[^a-zA-Z0-9_-]', '_', word_text)
                            crop_filename = f"crop_f{floor_no}_p{page_idx}_{clean_mark_file}_{w_idx}_{uuid.uuid4().hex[:6]}.png"
                            crop_path = os.path.join(settings.OUTPUT_DIR, crop_filename)
                            pix.save(crop_path)
                            
                            # Draw Red Target Pin on Crop
                            try:
                                img = Image.open(crop_path).convert("RGB")
                                draw = ImageDraw.Draw(img)
                                scale = 200.0 / 72.0
                                px_x = (mark_cx - clip_rect.x0) * scale
                                px_y = (mark_cy - clip_rect.y0) * scale
                                
                                # Red circle around target mark
                                r = 30
                                draw.ellipse([px_x - r, px_y - r, px_x + r, px_y + r], outline=(255, 0, 0), width=5)
                                
                                # Red pointer arrow pointing down-right at circle
                                draw.line([(px_x - 70, px_y - 70), (px_x - 25, px_y - 25)], fill=(255, 0, 0), width=6)
                                arrow_head = [(px_x - 20, px_y - 20), (px_x - 45, px_y - 22), (px_x - 22, px_y - 45)]
                                draw.polygon(arrow_head, fill=(255, 0, 0))
                                
                                img.save(crop_path)
                            except Exception as pin_err:
                                logger.warning(f"Could not draw red target pin on crop: {pin_err}")
                                
                            all_temp_crops.append(crop_path)
                            
                            # Queue LLM task for location/room name only
                            location_tasks.append((word_text, floor_no, floor_name, crop_path, opening_mode))
                        except Exception as crop_err:
                            logger.error(f"Failed to create crop for mark {word_text}: {crop_err}")
                            # Still record the programmatic result without location
                            detections.append({
                                "mark": word_text,
                                "location": "",
                                "opening_mode": opening_mode,
                                "int_ext": "Interior",
                                "floor_no": str(floor_no),
                                "floor_name": floor_name
                            })
                            
            doc.close()

        # Run location LLM tasks concurrently
        logger.info(f"CV Detector: Running {len(location_tasks)} location-detection LLM tasks...")
        
        async def run_location_task(mark, floor_no, floor_name, crop_path, opening_mode):
            location, int_ext = await get_location_from_crop(crop_path, mark, floor_no, semaphore)
            return {
                "mark": mark,
                "location": location,
                "opening_mode": opening_mode,  # programmatically determined
                "int_ext": int_ext,
                "floor_no": str(floor_no),
                "floor_name": floor_name
            }
        
        location_results = await asyncio.gather(
            *[run_location_task(m, f, fn, cp, om) for m, f, fn, cp, om in location_tasks]
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
