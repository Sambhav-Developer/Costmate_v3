import os
import json
import asyncio
import traceback
import base64
from functools import lru_cache
from PIL import Image, ImageDraw
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.services.graph.state import CostmateState
from app.core.logging import logger
from app.config import settings

try:
    import shapely
    from shapely.geometry import Point, LineString, MultiPolygon
    from shapely.ops import unary_union
    SHAPELY_AVAILABLE = True
except ModuleNotFoundError as e:
    SHAPELY_AVAILABLE = False
    logger.critical(
        "shapely is not installed — geometry engine disabled, "
        "ALL doors on this run will be forced to needs_review=True: %s", e
    )

# VLM door classification paths and helper functions
# Dynamically locate WORKSPACE_DIR containing the Assets folder
dir_path = os.path.dirname(os.path.abspath(__file__))
while dir_path:
    if os.path.exists(os.path.join(dir_path, "Assets")):
        break
    parent = os.path.dirname(dir_path)
    if parent == dir_path:
        break
    dir_path = parent
WORKSPACE_DIR = dir_path
REFERENCE_CATALOG_PATH = os.path.join(WORKSPACE_DIR, "Assets", "door_types_updated.png")

@lru_cache(maxsize=1)
def get_reference_catalog_b64() -> str:
    if not os.path.exists(REFERENCE_CATALOG_PATH):
        logger.warning(f"VLM: Reference catalog image not found at {REFERENCE_CATALOG_PATH}")
        return ""
    with open(REFERENCE_CATALOG_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

VALID_OPENING_MODES = {"SGL", "PR", "CO", "DA", "SLD", "PKT", "BIFOLD", "OHD", "REV", "BYPASS", "UNKNOWN"}
VALID_WALL_TYPES = {"INT", "EXT", "UNKNOWN"}

NON_DOOR_TAG_KEYWORDS = {
    "ROOM", "OFFICE", "WORKROOM", "CORRIDOR", "CORR", "STORAGE", "STO",
    "STAIR", "STA", "BEV", "BEVERAGE", "KITCHEN", "KIT", "RESTROOM", "RR",
    "TOILET", "BATH", "BATHROOM", "MECH", "MECHANICAL", "ELEC", "ELECTRICAL",
    "JAN", "JANITOR", "CLOSET", "CLO", "VEST", "VESTIBULE", "LOBBY", "HALL",
    "HALLWAY", "UTILITY", "UTIL", "BREAK", "CONF", "CONFERENCE", "ENTRY",
    "ENTRANCE", "WAITING", "RECEPTION", "SUITE", "DECK", "PATIO", "BALCONY",
    "GARAGE", "BASEMENT", "ATTIC", "ROOF", "ELEV", "ELEVATOR", "SHAFT",
    "PLAN", "DEVICES", "SYMBOLS", "AREAS", "FILL", "PATTERN", "WITH", "IN",
    "NO", "EX", "EXIST", "EXISTING", "NEW", "TYP", "TYPICAL", "SIM", "SIMILAR",
    "SDP", "CL", "N/A", "SEE", "NOTE", "NOTES", "DETAIL", "SECTION", "ELEVATION",
    "SCALE", "DATE", "DRAWN", "CHECKED", "SHEET", "NORTH", "SOUTH", "EAST",
    "WEST", "KEY", "LEGEND", "MARK", "MARKS", "QTY", "SIZE", "TYPE", "WALL",
    "DOOR", "DOORS", "FRAME", "FRAMES", "JAMB", "HEAD", "SILL", "FINISH",
    "SCHEDULE", "SPEC", "SPECS", "SPECIFICATION", "SPECIFICATIONS",
    "HARDWARE", "HW", "HDWR", "SET", "SETS", "BUTTS", "HINGES", "CLOSER",
    "CLOSERS", "LOCK", "LOCKSET", "LATCH", "STRIKE", "BOLT", "PANIC",
    "AND", "FOR", "THE", "ALL", "NOT", "PER", "BY", "FROM", "TO", "ON", "AT",
    "UP", "DN", "DOWN", "TOP", "BOT", "BOTTOM", "MAX", "MIN", "TOTAL",
    "ITEM", "ITEMS", "TAG", "TAGS", "REV", "REVISION", "RATING", "FIRE"
}

def is_valid_orphan_tag_candidate(word: str, sched_marks: set) -> bool:
    """Check if a word is a plausible orphan plan door tag candidate."""
    import re
    word_upper = word.upper().strip(".,()[]{}-_#*")
    if word_upper in NON_DOOR_TAG_KEYWORDS:
        return False
    if any(c in word for c in ['"', "'", '=', '/', '\\', '°']):
        return False
    if re.match(r'^[A-Z]?-\d+\.\d+$', word_upper) or re.match(r'^\d+\.\d+$', word_upper):
        return False
    if re.match(r'^[A-Z]\.\d+$', word_upper):
        return False
    if len(word_upper) == 1 and word_upper not in sched_marks:
        return False
    if re.match(r'^S\d+T\d+$', word_upper):
        return False
    return True


SYSTEM_PROMPT = """You are an expert civil construction estimation assistant.

You will be given two images:
1. A reference catalog image showing 10 standard door opening-type plan symbols, each labeled with its code (SGL, PR, CO, DA, SLD, PKT, BIFOLD, OHD, REV, BYPASS).
2. A cropped image from an architectural floor plan, centered exactly on the door opening of interest.

Your task is to analyze the door opening located directly at the center of the Crop Image, compare it against the Reference Catalog, and determine its properties.

Please classify the following fields:
- "matched_code": Identify which of the 10 reference codes the center door opening symbol most closely resembles. Select ONLY from: "SGL", "PR", "CO", "DA", "SLD", "PKT", "BIFOLD", "OHD", "REV", "BYPASS". If it does not resemble any of them, return "UNKNOWN".
  Classification tips for visual shapes:
  * "SGL" (Single Swing): One leaf, one quarter-circle arc. Very common.
  * "PR" (Pair Swing): Two mirrored leaves, two arcs meeting at the center (double doors).
  * "CO" (Cased Opening): Just jamb/trim lines, no swing arc line, no door leaf line (open doorway).
  * "DA" (Double Acting): Pivot dot with swing arc paths on both sides of the wall.
  * "SLD" (Sliding): Flat panel riding along the wall surface, often with a travel arrow.
  * "PKT" (Pocket Sliding): Sliding panel shown dashed, sliding inside the wall cavity.
  * "BIFOLD" (Bi-fold): Panels folding into a "V" shape.
- "wall_type": Classify whether the wall the door is sitting in is "INT" or "EXT".
  Tips for accuracy:
  * Read any wall tag symbols printed near the wall/door on the plan (e.g., tags like "6A.AL.EXT", "CMU.EXT", "6A.AL", "6A").
  * If the tag contains ".EXT" or "EXT" suffix, it is "EXT" (Exterior). If tag has ".INT", ".W", or no "EXT" suffix, it is "INT" (Interior).
  * Look for exterior-specific visual indicators: storefront systems, glazing/curtain wall framing, louvers, weatherstripping symbols, or exterior paving/ground hatching beyond the wall.
  * DO NOT rely on wall line thickness or line weight to determine interior vs exterior.
  * If no clear exterior features are present, return "INT" or "UNKNOWN".
- "location": Identify the room name/corridor name label printed inside or near the door opening space (e.g. "Office 101", "Corridor", "Staff Toilet"). If not visible, return "Unknown".
- "confidence": "high" | "medium" | "low" based on classification clarity.
- "reasoning": A short sentence explaining the graphic feature driving your matched_code match.

Return ONLY a clean JSON object:
{
  "matched_code": "SGL" | "PR" | "CO" | "DA" | "SLD" | "PKT" | "BIFOLD" | "OHD" | "REV" | "BYPASS" | "UNKNOWN",
  "wall_type": "INT" | "EXT" | "UNKNOWN",
  "location": "string",
  "confidence": "high" | "medium" | "low",
  "reasoning": "string"
}
"""

def validate_vlm_output(result: dict) -> dict:
    if not isinstance(result, dict):
        return {
            "matched_code": "UNKNOWN",
            "wall_type": "UNKNOWN",
            "location": "Unknown",
            "confidence": "low",
            "reasoning": "Invalid VLM response format"
        }
    
    if result.get("matched_code") not in VALID_OPENING_MODES:
        result["matched_code"] = "UNKNOWN"
    if result.get("wall_type") not in VALID_WALL_TYPES:
        result["wall_type"] = "UNKNOWN"
    if not result.get("location"):
        result["location"] = "Unknown"
        
    return result

async def classify_door_crop_vlm(crop_path: str, mark: str, floor_no: int, semaphore: asyncio.Semaphore) -> dict:
    """
    Call Qwen-VL vision agent to classify the crop opening mode and wall type side-by-side with reference catalog.
    """
    if not crop_path or not os.path.exists(crop_path):
        return {
            "matched_code": "UNKNOWN",
            "wall_type": "UNKNOWN",
            "location": "Unknown",
            "confidence": "low",
            "reasoning": "Missing crop path"
        }
        
    reference_b64 = get_reference_catalog_b64()
    if not reference_b64:
        return {
            "matched_code": "UNKNOWN",
            "wall_type": "UNKNOWN",
            "location": "Unknown",
            "confidence": "low",
            "reasoning": "Missing reference catalog b64"
        }

    # Normalize crop resolution to 400x400 px
    try:
        with Image.open(crop_path) as img:
            if img.size != (400, 400):
                img_resized = img.resize((400, 400), Image.Resampling.LANCZOS)
                img_resized.save(crop_path)
    except Exception as resize_err:
        logger.warning(f"VLM Guardrails: Failed to normalize crop resolution for {crop_path}: {resize_err}")

    async with semaphore:
        max_vlm_retries = 3
        for attempt in range(max_vlm_retries):
            try:
                res = await openrouter_client.generate_chat(
                    prompt=SYSTEM_PROMPT,
                    image_paths=[
                        f"data:image/png;base64,{reference_b64}" if REFERENCE_CATALOG_PATH.endswith(".png") else f"data:image/jpeg;base64,{reference_b64}",
                        crop_path
                    ],
                    json_mode=True,
                    temperature=0.1,
                    model_name="qwen/qwen2.5-vl-72b-instruct"
                )
                data = parse_json_response(res)
                return validate_vlm_output(data)
            except Exception as e:
                if attempt < max_vlm_retries - 1:
                    logger.warning(f"VLM: Mark {mark} Floor {floor_no} failed (Attempt {attempt+1}/{max_vlm_retries}): {e}. Retrying in 2s...")
                    await asyncio.sleep(2.0)
                else:
                    logger.error(f"VLM: Vision classification exhausted retries for mark {mark} on Floor {floor_no}: {e}")
                    return {
                        "matched_code": "UNKNOWN",
                        "wall_type": "UNKNOWN",
                        "location": "Unknown",
                        "confidence": "low",
                        "reasoning": f"Vision API error: {str(e)}"
                    }


# Common room keywords to filter out room name labels from door/window callouts
ROOM_KEYWORDS = {
    "room", "rm", "office", "toilet", "staff", "holding", "treatment", "bed", 
    "lounge", "lobby", "corridor", "hall", "stair", "storage", 
    "mech", "electrical", "elec", "janitor", "closet", "bath", "shower", "wc", 
    "vestibule", "entry", "exit", "classroom", "kitchen", "conf", "conference", 
    "shared", "hvac", "elevator", "utility", "laundry", "nourse", "care", "station",
    "exam", "examination", "it", "pantry", "waiting", "reception", "soiled", "clean", 
    "nurse", "nook", "dictation", "physician", "touchdown", "med", "meds", "unisex", 
    "vest", "clos", "lrd", "sub", "wait", "consult", "consultation", "work", "lockers", 
    "triage", "harrison", "mamaroneck", "shwr", "toilet/shwr", "cr", "com", "crm"
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
                if 0 <= gap < 2.5:
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

def is_block_room_label(blocks, block_no, line_no, clean_mark) -> bool:
    if block_no < 0 or block_no >= len(blocks):
        return False
    try:
        b = blocks[block_no]
        block_text = b[4]
        # Check if the entire block contains any room keywords (handles room numbers grouped with room names)
        block_words = [w.strip(".,()[]{}-_#*/").lower() for w in block_text.split() if w]
        if any(kw in block_words for kw in ROOM_KEYWORDS):
            return True
            
        lines = block_text.split("\n")
        if 0 <= line_no < len(lines):
            line_text = lines[line_no].strip().upper()
            line_words = [w.strip(".,()[]{}-_#*/").lower() for w in line_text.split() if w]
            if any(kw in line_words for kw in ROOM_KEYWORDS):
                return True
        return False
    except Exception:
        return False

def is_stacked_door_callout(w, words_on_page) -> bool:
    """
    Checks if candidate word `w` is part of a multi-cell door callout tag stack (e.g. D1 / 36" / MARK).
    Looks for door type/width indicator words ('D1', 'D2', '36"', '45') stacked directly above `w`.
    """
    w_cx = (w[0] + w[2]) / 2.0
    w_top = w[1]
    for other_w in words_on_page:
        other_txt = other_w[4].strip(".,()[]{}-_#*").upper()
        if any(tag in other_txt for tag in ["D1", "D2", "D3", "36", "45", "MARK"]):
            other_cx = (other_w[0] + other_w[2]) / 2.0
            other_bot = other_w[3]
            if abs(other_cx - w_cx) <= 25.0 and 0.0 <= (w_top - other_bot) <= 35.0:
                return True
    return False

def is_combined_room_name_and_mark(w, words_on_page) -> bool:
    """
    STEP 2 Sub-Pattern 2A Pre-Filter:
    Checks if candidate word `w` is part of a combined Room Name + Mark string on the same text line
    (e.g., 'OFFICE HE210V', 'SOCIAL WORK OFFICE 103', 'EXAM 300-08', 'IT ROOM 105B').
    """
    w_cx = (w[0] + w[2]) / 2.0
    w_cy = (w[1] + w[3]) / 2.0
    
    for other_w in words_on_page:
        if other_w == w:
            continue
        other_txt = other_w[4].strip(".,()[]{}-_#*/").lower()
        if any(kw in other_txt for kw in ROOM_KEYWORDS):
            other_cy = (other_w[1] + other_w[3]) / 2.0
            other_cx = (other_w[0] + other_w[2]) / 2.0
            # Same line vertical alignment (within 6pt) and close horizontal proximity (within 120pt)
            if abs(other_cy - w_cy) <= 6.0 and abs(other_cx - w_cx) <= 120.0:
                return True
    return False

def is_room_container_area_block(w_rect, words_on_page) -> bool:
    """
    STEP 2 Sub-Pattern 2B Pre-Filter & Unit-Type Differentiator:
    Checks if candidate word `w` is part of a multi-cell Room Tag container box (e.g. '105B' paired with '7 SF').
    Differentiates Room Blocks from Genuine Door Grid-Tables by inspecting secondary cell unit types:
      - ROOM BLOCK (DROP): Secondary cell contains area units ('SF', 'SQ FT', 'SQFT', 'M2', 'S.F.').
      - DOOR GRID-TABLE (KEEP): Secondary cell contains door dimensions ('36"', '3\'-0"', '45"', 'D1', 'D2', 'MARK').
    """
    import fitz
    search_rect = fitz.Rect(w_rect) + (-35.0, -35.0, 35.0, 35.0)
    
    AREA_UNITS = {"sf", "sqft", "sq ft", "sq.ft", "m2", "sq m", "s.f.", "area"}
    DOOR_UNITS = {"d1", "d2", "d3", "36", "45", "30", "mark", "type", "leaf"}
    
    found_area_unit = False
    found_door_unit = False
    
    for other_w in words_on_page:
        r_other = fitz.Rect(other_w[:4])
        if search_rect.intersects(r_other):
            txt = other_w[4].strip(".,()[]{}-_#*/\"'").lower()
            if txt in AREA_UNITS or any(au in txt for au in ["sf", "sqft", "sq.ft"]):
                found_area_unit = True
            if txt in DOOR_UNITS or any(du in txt for du in ["36\"", "3'-0\"", "d1", "d2"]):
                found_door_unit = True
                
    # If explicit door dimension unit is present (e.g. D1 / 36" / mark), NEVER treat as room block
    if found_door_unit:
        return False
    return found_area_unit

def is_hinge_anchor_dot_connected(w_rect, drawings, r_min=1.0, r_max=4.0) -> bool:
    """
    STEP 3 Attachment & Anchor Test Rule 3C:
    Checks if a small circular marker (radius r in [1.0, 4.0] pt, diameter 2.0-8.0 pt) sits at the arc hinge/springpoint
    and is connected via leader line to candidate text w_rect (e.g. RS030, RS036).
    """
    import fitz
    search_rect = fitz.Rect(w_rect) + (-60.0, -60.0, 60.0, 60.0)
    if not drawings:
        return False
    
    for d in drawings:
        rect = d.get("rect")
        if not rect:
            continue
        r = fitz.Rect(rect)
        if not search_rect.intersects(r):
            continue
            
        w, h = r.width, r.height
        radius = (w + h) / 4.0
        if r_min <= radius <= r_max and abs(w - h) <= 2.0:
            items = d.get("items", [])
            has_curve = any(it[0] in ("c", "qu", "v", "y") for it in items)
            if has_curve:
                return True
    return False

def detect_wall_endcap_jamb_signature(crop_rect, drawings) -> bool:
    """
    STEP 3 Cased Opening Jamb Signature:
    Detects parallel wall jamb lines WITH short perpendicular end-cap / return lines
    closing wall thickness at opening boundary.
    """
    import fitz
    if not drawings:
        return False
    c_rect = fitz.Rect(crop_rect)
    short_perp_segments = 0
    
    for d in drawings:
        rect = d.get("rect")
        if not rect:
            continue
        r = fitz.Rect(rect)
        if c_rect.intersects(r):
            w, h = r.width, r.height
            # End-cap return lines are very short wall-break perpendicular segments (width/height <= 12pt)
            if (w <= 12.0 and h <= 4.0) or (h <= 12.0 and w <= 4.0):
                short_perp_segments += 1
                
    return short_perp_segments >= 2

def compute_min_dist_to_door_arc(w_cx, w_cy, drawings) -> float:
    """
    Computes minimum Euclidean distance from candidate text center (w_cx, w_cy) to nearest swing arc curve item.
    """
    min_dist = 999.0
    if not drawings:
        return min_dist

    # Polyline chain arcs check
    poly_arcs = find_polyline_chain_arcs(drawings, (w_cx, w_cy), radius=60.0)
    for arc in poly_arcs:
        arc_cx, arc_cy = arc["center"]
        dist = ((arc_cx - w_cx)**2 + (arc_cy - w_cy)**2)**0.5
        min_dist = min(min_dist, dist)
        for pt in arc["points"]:
            pt_d = ((pt.x - w_cx)**2 + (pt.y - w_cy)**2)**0.5
            min_dist = min(min_dist, pt_d)

    for d in drawings:
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu", "v", "y") for it in items)
        rect = d.get("rect")
        if not rect:
            continue
            
        rx0, ry0, rx1, ry1 = rect[0], rect[1], rect[2], rect[3]
        dx = max(rx0 - w_cx, 0, w_cx - rx1)
        dy = max(ry0 - w_cy, 0, w_cy - ry1)
        rect_dist = (dx**2 + dy**2)**0.5
        
        if has_curve:
            arc_cx = (rx0 + rx1) / 2.0
            arc_cy = (ry0 + ry1) / 2.0
            center_dist = ((arc_cx - w_cx) ** 2 + (arc_cy - w_cy) ** 2) ** 0.5
            effective_dist = min(rect_dist, center_dist)
            if effective_dist < min_dist:
                min_dist = effective_dist
    return min_dist

def is_enclosed_in_tag_circle(w_cx, w_cy, nearby_drawings) -> bool:
    """
    Check if a word's center is enclosed by a small circle vector path (typical door tag circle).
    """
    for d in nearby_drawings:
        rect = d.get("rect")
        if not rect:
            continue
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        
        # Check if it's a small square/circle bounding box (typically diameter 12-35 pt)
        if 12.0 <= width <= 35.0 and 12.0 <= height <= 35.0 and abs(width - height) <= 4.0:
            draw_cx = (rect[0] + rect[2]) / 2
            draw_cy = (rect[1] + rect[3]) / 2
            dist = ((draw_cx - w_cx) ** 2 + (draw_cy - w_cy) ** 2) ** 0.5
            # Word center should be very close to the circle center
            if dist <= 12.0:
                items = d.get("items", [])
                has_curve = any(it[0] in ("c", "qu") for it in items)
                if has_curve:
                    return True
    return False

def find_door_tag_shapes(drawings, proximity_threshold: float = 4.0) -> list:
    """
    Detect Door Tag Shapes via Vector Path Spatial Clustering & Merging.
    Groups adjacent/overlapping vector paths and line segments (internal cell dividers + outer boxes)
    within proximity_threshold into composite candidate rects before filtering by size & attachment.
    Shape-agnostic: handles grid tables, circles, ovals, hexagons, and rectangles uniformly without branching.
    Returns list of composite fitz.Rect regions.
    """
    import fitz
    if not drawings:
        return []
    
    # 1. Collect individual vector path bounding boxes within reasonable segment size limits
    raw_rects = []
    for d in drawings:
        rect = d.get("rect")
        if not rect:
            continue
        r = fitz.Rect(rect)
        w, h = r.width, r.height
        if 2.0 <= w <= 90.0 and 2.0 <= h <= 90.0:
            has_fill = d.get("fill") is not None
            items = d.get("items", [])
            # Exclude solid-color filled pills/rounded rectangles with no internal cell lines
            if has_fill and len(items) <= 2:
                continue
            raw_rects.append(r)
            
    if not raw_rects:
        return []
        
    # 2. Spatial Clustering: Merge overlapping/adjacent rects within proximity_threshold
    clusters = []
    for r in raw_rects:
        expanded_r = r + (-proximity_threshold, -proximity_threshold, proximity_threshold, proximity_threshold)
        matching_indices = []
        for i, c in enumerate(clusters):
            if c.intersects(expanded_r):
                matching_indices.append(i)
                
        if not matching_indices:
            clusters.append(r)
        else:
            # Union all matching clusters with current rect
            merged = r
            for i in reversed(matching_indices):
                merged = merged | clusters.pop(i)
            clusters.append(merged)
            
    # 3. Filter composite merged candidate rects
    candidate_rects = []
    for c in clusters:
        if 10.0 <= c.width <= 90.0 and 10.0 <= c.height <= 90.0:
            candidate_rects.append(c)
            
    return candidate_rects


def point_dist_to_rect(p, r) -> float:
    """Computes minimum distance between a point (fitz.Point or tuple) and a fitz.Rect."""
    px = p.x if hasattr(p, 'x') else p[0]
    py = p.y if hasattr(p, 'y') else p[1]
    dx = max(r.x0 - px, 0, px - r.x1)
    dy = max(r.y0 - py, 0, py - r.y1)
    return (dx**2 + dy**2)**0.5

def safe_extract_curve_points(item):
    """Safely extracts endpoint fitz.Point objects from PyMuPDF curve commands."""
    import fitz
    if len(item) < 3:
        return None, None
    p1 = item[1]
    p3 = item[3] if len(item) > 3 else item[2]
    if not hasattr(p1, 'x') and isinstance(p1, (list, tuple)) and len(p1) >= 2:
        p1 = fitz.Point(p1[0], p1[1])
    if not hasattr(p3, 'x') and isinstance(p3, (list, tuple)) and len(p3) >= 2:
        p3 = fitz.Point(p3[0], p3[1])
    if hasattr(p1, 'x') and hasattr(p3, 'x'):
        return p1, p3
    return None, None

def safe_extract_line_points(item):
    """Safely extracts endpoint fitz.Point objects from PyMuPDF line commands."""
    import fitz
    if len(item) < 3:
        return None, None
    p1, p2 = item[1], item[2]
    if not hasattr(p1, 'x') and isinstance(p1, (list, tuple)) and len(p1) >= 2:
        p1 = fitz.Point(p1[0], p1[1])
    if not hasattr(p2, 'x') and isinstance(p2, (list, tuple)) and len(p2) >= 2:
        p2 = fitz.Point(p2[0], p2[1])
    if hasattr(p1, 'x') and hasattr(p2, 'x'):
        return p1, p2
    return None, None

def find_polyline_chain_arcs(drawings, center_pt, radius=50.0) -> list:
    """
    Reconstructs polyline-approximated door swing arcs from chains of short 'l' line segments.
    Applies:
      1. Density pre-check: requires >= 8 short 'l' segments (len <= 6.0pt) within search radius.
      2. Endpoint chaining: links consecutive 'l' segments matching endpoints within <= 1.5pt.
      3. Total chain length filter: 12.0 <= chain_length <= 160.0 pt.
      4. Monotonic curvature check: >= 68% uniform turn direction & cumulative rotation >= 0.18 rad (rejects hatching/fill grids).
    Returns list of dicts describing valid reconstructed polyline arcs:
      [{"rect": fitz.Rect, "points": [p0, p1, ...], "total_length": float, "center": (cx, cy)}]
    """
    import fitz
    import math

    cx = center_pt.x if hasattr(center_pt, 'x') else center_pt[0]
    cy = center_pt.y if hasattr(center_pt, 'y') else center_pt[1]
    search_rect = fitz.Rect(cx - radius, cy - radius, cx + radius, cy + radius)

    if not drawings:
        return []

    # Step 1: Cheap density pre-check
    short_segments = []
    all_candidate_lines = []

    for d in drawings:
        d_rect = d.get("rect")
        if not d_rect:
            continue
        r = fitz.Rect(d_rect)
        if not search_rect.intersects(r):
            continue

        for item in d.get("items", []):
            if item[0] == "l":
                p1, p2 = safe_extract_line_points(item)
                if p1 and p2:
                    l_len = ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                    if search_rect.contains(p1) or search_rect.contains(p2):
                        all_candidate_lines.append((p1, p2, l_len))
                        if l_len <= 6.0:
                            short_segments.append((p1, p2, l_len))

    # Fast signal density proxy: require >= 8 short segments within radius
    if len(short_segments) < 8:
        return []

    # Step 2: Chain Reconstruction (link consecutive 'l' segments with matching endpoints within 1.5pt)
    lines_pool = list(all_candidate_lines)
    used = [False] * len(lines_pool)
    chains = []

    def pt_dist(ptA, ptB):
        return ((ptA.x - ptB.x)**2 + (ptA.y - ptB.y)**2)**0.5

    for i in range(len(lines_pool)):
        if used[i]:
            continue

        p1, p2, l_len = lines_pool[i]
        used[i] = True
        curr_chain = [p1, p2]
        chain_len = l_len

        # Grow forward from curr_chain[-1]
        growing = True
        while growing:
            growing = False
            tip = curr_chain[-1]
            best_idx = -1
            best_dist = 1.6  # 1.5pt tolerance
            best_flip = False

            for j in range(len(lines_pool)):
                if used[j]:
                    continue
                lp1, lp2, llen = lines_pool[j]
                d1 = pt_dist(tip, lp1)
                d2 = pt_dist(tip, lp2)
                if d1 < best_dist:
                    best_dist = d1
                    best_idx = j
                    best_flip = False
                if d2 < best_dist:
                    best_dist = d2
                    best_idx = j
                    best_flip = True

            if best_idx != -1:
                used[best_idx] = True
                lp1, lp2, llen = lines_pool[best_idx]
                nxt_pt = lp1 if best_flip else lp2
                curr_chain.append(nxt_pt)
                chain_len += llen
                growing = True

        # Grow backward from curr_chain[0]
        growing = True
        while growing:
            growing = False
            tail = curr_chain[0]
            best_idx = -1
            best_dist = 1.6  # 1.5pt tolerance
            best_flip = False

            for j in range(len(lines_pool)):
                if used[j]:
                    continue
                lp1, lp2, llen = lines_pool[j]
                d1 = pt_dist(tail, lp1)
                d2 = pt_dist(tail, lp2)
                if d1 < best_dist:
                    best_dist = d1
                    best_idx = j
                    best_flip = True
                if d2 < best_dist:
                    best_dist = d2
                    best_idx = j
                    best_flip = False

            if best_idx != -1:
                used[best_idx] = True
                lp1, lp2, llen = lines_pool[best_idx]
                prev_pt = lp2 if best_flip else lp1
                curr_chain.insert(0, prev_pt)
                chain_len += llen
                growing = True

        if len(curr_chain) >= 4 and 12.0 <= chain_len <= 160.0:
            chains.append((curr_chain, chain_len))

    # Step 3: Curvature check (monotonically changing turn angles)
    valid_arcs = []
    for chain_pts, total_len in chains:
        angles = []
        for k in range(len(chain_pts) - 1):
            dx = chain_pts[k+1].x - chain_pts[k].x
            dy = chain_pts[k+1].y - chain_pts[k].y
            if dx == 0 and dy == 0:
                continue
            angles.append(math.atan2(dy, dx))

        if len(angles) < 3:
            continue

        turn_angles = []
        for k in range(len(angles) - 1):
            diff = angles[k+1] - angles[k]
            while diff > math.pi: diff -= 2 * math.pi
            while diff < -math.pi: diff += 2 * math.pi
            turn_angles.append(diff)

        if not turn_angles:
            continue

        pos_turns = sum(1 for t in turn_angles if t > 0.01)
        neg_turns = sum(1 for t in turn_angles if t < -0.01)
        non_zero = pos_turns + neg_turns
        if non_zero == 0:
            continue

        dominant_ratio = max(pos_turns, neg_turns) / float(non_zero)
        cum_rotation = abs(sum(turn_angles))

        if dominant_ratio >= 0.68 and cum_rotation >= 0.18:
            xs = [p.x for p in chain_pts]
            ys = [p.y for p in chain_pts]
            arc_rect = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
            arc_cx = sum(xs) / len(xs)
            arc_cy = sum(ys) / len(ys)
            valid_arcs.append({
                "rect": arc_rect,
                "points": chain_pts,
                "total_length": total_len,
                "center": (arc_cx, arc_cy)
            })

    return valid_arcs

def is_tag_attached_to_door_opening(tag_rect, drawings, radius=45.0) -> bool:
    """
    STEP 2: Confirm candidate tag region is structurally attached to door opening geometry.
    Tests if tag_rect touches or overlaps:
      a) Wall-break / jamb hardware tick icon at arc origin
      b) Actual arc curve polyline / Bezier points
      c) Cased opening jamb lines
    """
    import fitz
    search_rect = tag_rect + (-radius, -radius, radius, radius)
    if not drawings:
        return False

    # Check polyline-chain arcs first
    tag_center = ((tag_rect.x0 + tag_rect.x1) / 2.0, (tag_rect.y0 + tag_rect.y1) / 2.0)
    poly_arcs = find_polyline_chain_arcs(drawings, tag_center, radius=radius)
    if poly_arcs:
        for arc in poly_arcs:
            if point_dist_to_rect(fitz.Point(arc["center"]), tag_rect) <= 45.0:
                return True
            for pt in arc["points"]:
                if point_dist_to_rect(pt, tag_rect) <= 30.0:
                    return True

    for d in drawings:
        d_rect = fitz.Rect(d.get("rect", [0, 0, 0, 0]))
        if not search_rect.intersects(d_rect):
            continue
            
        items = d.get("items", [])
        for item in items:
            cmd = item[0]
            # Check a) Curve path points (Bezier or arc)
            if cmd in ("c", "v", "y", "qu"):
                p1, p3 = safe_extract_curve_points(item)
                if p1 and p3:
                    c_len = ((p3.x - p1.x)**2 + (p3.y - p1.y)**2)**0.5
                    if 10.0 <= c_len <= 180.0:
                        p_mid = fitz.Point((p1.x + p3.x)/2, (p1.y + p3.y)/2)
                        if point_dist_to_rect(p1, tag_rect) <= 35.0 or point_dist_to_rect(p3, tag_rect) <= 35.0 or point_dist_to_rect(p_mid, tag_rect) <= 35.0:
                            return True
            # Check b) Jamb lines / double-tick hardware icons
            elif cmd == "l":
                p1, p2 = safe_extract_line_points(item)
                if p1 and p2:
                    l_len = ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                    if 8.0 <= l_len <= 140.0:
                        p_mid = fitz.Point((p1.x + p2.x)/2, (p1.y + p2.y)/2)
                        if point_dist_to_rect(p_mid, tag_rect) <= 30.0:
                            return True
    return False

def is_solid_color_room_pill(inst_rect, drawings_on_page) -> bool:
    """
    STEP 5 Rule: Returns True if inst_rect is inside a solid-color filled pill/bubble 
    with no internal cell lines and is not attached to door opening geometry.
    """
    import fitz
    if not drawings_on_page:
        return False
    for d in drawings_on_page:
        rect = d.get("rect")
        if not rect:
            continue
        d_r = fitz.Rect(rect)
        if d_r.intersects(inst_rect):
            has_fill = d.get("fill") is not None
            items = d.get("items", [])
            if has_fill and len(items) <= 2:
                if not is_tag_attached_to_door_opening(d_r, drawings_on_page):
                    return True
    return False

def validate_vector_opening_geometry(page, point, radius=40.0, return_details=False, drawings=None):
    """
    Validates if candidate text at `point` (fitz.Point or (cx, cy)) represents a genuine door opening tag.
    Checks 3 complementary CAD/PDF vector drawing criteria within tight `radius` (40pt ~ 0.55 inches):
      Criterion A: Swing Arcs (single or pair cubic Bezier curves 'c', 'v', 'y' or polyline-chain arcs)
      Criterion B: Cased Opening Frame Lines & Wall Gap Terminations
      Criterion C: Vector Callout Bubble Shape (circle/oval/hexagon) or Leader Line
    """
    import fitz
    cx = point.x if hasattr(point, 'x') else point[0]
    cy = point.y if hasattr(point, 'y') else point[1]
    
    search_rect = fitz.Rect(cx - radius, cy - radius, cx + radius, cy + radius)
    if drawings is None:
        try:
            drawings = page.get_drawings()
        except Exception:
            if return_details:
                return True, 0, 0.0, 0, 0.0
            return True # Fallback if drawings stream unavailable
        
    has_arc = False
    has_cased_jamb = False
    has_callout_shape = False

    n_line_segments = 0
    max_l_len = 0.0
    n_curve_segments = 0
    max_c_len = 0.0
    
    for path in drawings:
        p_rect = fitz.Rect(path["rect"])
        if not search_rect.intersects(p_rect):
            continue
            
        w = p_rect.x1 - p_rect.x0
        h = p_rect.y1 - p_rect.y0
        
        # Criterion C: Enclosed Callout Symbol / Bubble around text or Leader Line
        if 10.0 <= w <= 65.0 and 10.0 <= h <= 65.0:
            d_cx = (p_rect.x0 + p_rect.x1) / 2.0
            d_cy = (p_rect.y0 + p_rect.y1) / 2.0
            if ((d_cx - cx)**2 + (d_cy - cy)**2)**0.5 <= 35.0:
                items = path.get("items", [])
                has_curve = any(it[0] in ("c", "qu", "v", "y") for it in items)
                if has_curve:
                    has_callout_shape = True
                    
        # Check item-level callout curves and leader lines attached to tag
        for item in path.get("items", []):
            cmd = item[0]
            if cmd in ("c", "qu", "v", "y"):
                p1, p3 = safe_extract_curve_points(item)
                if p1 and p3:
                    c_len = ((p3.x - p1.x)**2 + (p3.y - p1.y)**2)**0.5
                    d1 = ((p1.x - cx)**2 + (p1.y - cy)**2)**0.5
                    d3 = ((p3.x - cx)**2 + (p3.y - cy)**2)**0.5
                    if min(d1, d3) <= 30.0 and 5.0 <= c_len <= 35.0:
                        has_callout_shape = True
            elif cmd == "l":
                p1, p2 = safe_extract_line_points(item)
                if p1 and p2:
                    l_len = ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                    d1 = ((p1.x - cx)**2 + (p1.y - cy)**2)**0.5
                    d2 = ((p2.x - cx)**2 + (p2.y - cy)**2)**0.5
                    if min(d1, d2) <= 35.0 and l_len >= 15.0:
                        has_callout_shape = True
                
        for item in path.get("items", []):
            cmd = item[0]
            # Criterion A: Swing arcs (single or pair Bezier curves)
            if cmd in ("c", "v", "y"):
                n_curve_segments += 1
                p1, p3 = safe_extract_curve_points(item)
                if p1 and p3:
                    c_len = ((p3.x - p1.x)**2 + (p3.y - p1.y)**2)**0.5
                    if c_len > max_c_len:
                        max_c_len = c_len
                    if 12.0 <= c_len <= 160.0:
                        arc_cx = (p1.x + p3.x) / 2.0
                        arc_cy = (p1.y + p3.y) / 2.0
                        dist_to_arc = ((arc_cx - cx)**2 + (arc_cy - cy)**2)**0.5
                        if dist_to_arc <= 55.0:
                            has_arc = True
            # Criterion B: Straight lines for door panel or cased opening frame jambs
            elif cmd == "l":
                n_line_segments += 1
                p1, p2 = safe_extract_line_points(item)
                if p1 and p2:
                    l_len = ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                    if l_len > max_l_len:
                        max_l_len = l_len
                    if 15.0 <= l_len <= 140.0:
                        line_cx = (p1.x + p2.x) / 2.0
                        line_cy = (p1.y + p2.y) / 2.0
                        if ((line_cx - cx)**2 + (line_cy - cy)**2)**0.5 <= 45.0:
                            has_cased_jamb = True

    # Also check polyline chain arcs (CAD exporter polyline-approximated arcs)
    polyline_arcs = find_polyline_chain_arcs(drawings, (cx, cy), radius=radius)
    if polyline_arcs:
        has_arc = True

    valid = has_arc or has_cased_jamb or has_callout_shape
    if return_details:
        return valid, n_line_segments, max_l_len, n_curve_segments, max_c_len
    return valid

def normalize_opening_mode(val: str) -> str:
    val_clean = str(val).strip().upper()
    if val_clean in ["SINGLE", "SGL", "SINGLE-LEAF", "SINGLE LEAF", "1"]:
        return "SGL"
    if val_clean in ["DA", "DOUBLE ACTING", "DOUBLE-ACTING", "DOUBLE_ACTING"]:
        return "DA"
    if val_clean in ["DE", "DOUBLE EGRESS", "DOUBLE-EGRESS", "DOUBLE_EGRESS"]:
        return "DE"
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


def classify_opening_from_schedule(item: dict) -> str:
    """
    Layer 1 Schedule Fact Classifier: Evaluates user-confirmed schedule specs.
    Returns: 'STOREFRONT', 'PR', 'CO', 'DA', 'SGL', or 'UNKNOWN'
    """
    if not item or not isinstance(item, dict):
        return "UNKNOWN"
        
    mat = ""
    dtype = ""
    ftype = ""
    comments = ""
    w_a = ""
    w_b = ""
    p2_type = ""
    frame_mat = ""
    for k, v in item.items():
        kl = str(k).lower().strip()
        val_str = str(v).strip().upper()
        if not val_str or val_str in ["-", "N/A", "NONE", "NA"]:
            continue

        if "material" in kl and "door" in kl:
            mat = val_str
        elif "material" in kl and "frame" in kl:
            frame_mat = val_str
        elif "material" in kl and not mat:
            mat = val_str
        elif kl in ["door type", "type", "door panel 1 type", "panel 1 type"]:
            dtype = val_str
        elif kl in ["door panel 2 type", "panel 2 type", "panel type 2"]:
            p2_type = val_str
        elif "frame type" in kl:
            ftype = val_str
        elif kl in ["comments", "remarks", "estimator notes", "description"]:
            comments = val_str
        elif any(x in kl for x in ["width 1", "panel 1 width", "door panel 1 width", "leaf 1", "width a", "width_a", "w_a", "wa"]) or (kl == "width"):
            if not w_a: w_a = val_str
        elif any(x in kl for x in ["width 2", "panel 2 width", "door panel 2 width", "leaf 2", "width b", "width_b", "w_b", "wb"]):
            if not w_b: w_b = val_str

    storefront_tokens = ["AL", "ALUM", "ALUMINUM", "GLASS", "GL", "STOREFRONT", "CW", "CURTAINWALL"]
    if mat in storefront_tokens or frame_mat in storefront_tokens or any(tok in comments for tok in ["STOREFRONT", "AD SYSTEM", "ALUMINUM"]):
        return "STOREFRONT"

    # Pair Door (PR) Detection:
    # 1. Both Width 1 & Width 2 are populated
    # 2. Panel 2 Type is populated
    # 3. Type or comments contain PAIR, PR, DOUBLE, DBL
    if (w_a and w_b) or p2_type or any(p in dtype for p in ["PR", "PAIR", "DOUBLE", "DBL"]) or any(p in comments for p in ["PR", "PAIR", "DOUBLE"]):
        return "PR"

    if mat in ["NONE", "N/A", "CASED OPENING"] and dtype in ["CO", "NONE", "N/A", "CASED OPENING", "CASED"]:
        return "CO"
    if dtype in ["CO", "CASED OPENING", "CASED"]:
        return "CO"

    da_phrases = ["DBL ACT", "DBL-ACT", "DOUBLE ACTING", "DOUBLE-ACTING", "DOUBLE ACT", "DOUBLE-ACT", "ANTI-BARRICADE", "ANTI - BARRICADE"]
    da_exact_words = {"DA", "AB"}
    dtype_upper = dtype.upper()
    comments_upper = comments.upper()
    dtype_words = {w.strip(".,()[]{}-_#*") for w in dtype_upper.split()}
    comments_words = {w.strip(".,()[]{}-_#*") for w in comments_upper.split()}
    if (any(p in dtype_upper for p in da_phrases) or 
        any(p in comments_upper for p in da_phrases) or 
        da_exact_words.intersection(dtype_words) or 
        da_exact_words.intersection(comments_words)):
        return "DA"

    if w_a:
        return "SGL"

    return "UNKNOWN"

def classify_opening_from_drawings(drawings_near: list, mark_rect, item: dict = None) -> str:
    """
    Layer 2 CAD Vector Geometry Classifier: Analyzes raw PDF vector paths in 65pt radius.
    """
    import fitz as fz

    # 1. Rule 1: Check raw schedule facts FIRST.
    if item and isinstance(item, dict):
        l1 = classify_opening_from_schedule(item)
        if l1 != "UNKNOWN":
            logger.info(f"CV Drawing Analysis: Schedule indicates opening mode -> {l1}")
            return l1

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
    # 3. Rule 3: Progressive Multi-Radius Arc Collection (25pt baseline -> 45pt -> 65pt fallback)
    def collect_arcs_for_radius(r_limit):
        collected = []
        poly_arcs = find_polyline_chain_arcs(drawings_near, (mark_cx, mark_cy), radius=r_limit)
        for arc in poly_arcs:
            arc_cx, arc_cy = arc["center"]
            dist = ((arc_cx - mark_cx) ** 2 + (arc_cy - mark_cy) ** 2) ** 0.5
            if dist <= r_limit:
                collected.append({"rect": arc["rect"], "cx": arc_cx, "cy": arc_cy, "dist": dist})

        for d in drawings_near:
            items = d.get("items", [])
            has_curve = any(it[0] in ("c", "qu") for it in items)
            if not has_curve:
                continue

            arc_rect = fz.Rect(d.get("rect"))
            arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
            arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
            dist = ((arc_cx - mark_cx) ** 2 + (arc_cy - mark_cy) ** 2) ** 0.5

            if dist > r_limit:
                continue

            # Skip tiny mark-label annotation bubble arcs
            arc_area = arc_rect.width * arc_rect.height
            if dist < 15 and arc_area < 200:
                continue

            collected.append({"rect": arc_rect, "cx": arc_cx, "cy": arc_cy, "dist": dist})
        return collected

    arc_paths = []
    used_radius = 25.0
    for r_check in [25.0, 45.0, 65.0]:
        candidate_arcs = collect_arcs_for_radius(r_check)
        if candidate_arcs:
            arc_paths = candidate_arcs
            used_radius = r_check
            logger.info(f"CV Drawing Analysis: Found {len(arc_paths)} arc curve(s) at tight radius {r_check}pt.")
            break

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
    logger.info(f"CV Drawing Analysis: {distinct_leaves} distinct door leaf group(s) at radius {used_radius}pt -> {'PR' if distinct_leaves >= 2 else 'SGL'}")

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
    # 1. Primary check: exact door/window mark column headers
    for k, v in item.items():
        kl = str(k).lower().strip()
        if kl in ["mark", "mark no", "mark no.", "door mark", "door mark no", "dr mark", "window mark", "opening mark", "mark id", "tag", "mark / type", "mark/type"]:
            if v and str(v).strip():
                return str(v).strip().upper()
                
    # 2. Key contains 'mark' (excluding panel mark or finish mark)
    for k, v in item.items():
        kl = str(k).lower().strip()
        if "mark" in kl and not any(ex in kl for ex in ["panel", "finish", "frame", "hardware"]):
            if v and str(v).strip():
                return str(v).strip().upper()
                
    # 3. Fallback: Key equals 'type' or 'id'
    for k, v in item.items():
        kl = str(k).lower().strip()
        if kl in ["type", "id", "no", "no."]:
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
        logger.warning("No schedule items found in state — scanning floor plans for Orphan Plan Tags...")

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
                    
                    # Scenario 2 (SKILL.md): Discover Orphan Plan Tags (tags touching valid door geometry missing from schedule)
                    # ONLY run orphan tag discovery when NO schedule marks were provided in intake (schedule-less mode)!
                    if not matched_mark and not sched_marks and 1 <= len(raw_word) <= 8 and (raw_word.isalnum() or "-" in raw_word):
                        if is_valid_orphan_tag_candidate(raw_word, sched_marks):
                            if not is_combined_room_name_and_mark(w, words_on_page) and not is_room_container_area_block((w[0], w[1], w[2], w[3]), words_on_page):
                                w_cx = (w[0] + w[2]) / 2.0
                                w_cy = (w[1] + w[3]) / 2.0
                                if validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0, drawings=drawings_on_page):
                                    matched_mark = raw_word
                                    logger.info(f"CV Detector: Discovered Orphan Plan Tag '{raw_word}' at ({w_cx:.1f}, {w_cy:.1f}) touching door geometry")

                    if matched_mark:
                        word_text = matched_mark
                        w_x, w_y = w[0], w[1]
                        w_cx = (w[0] + w[2]) / 2
                        w_cy = (w[1] + w[3]) / 2
                        
                        # Filter out gridline bubbles and sheet borders in the outer 3% margins (using cropbox coordinate space)
                        crop_box = getattr(page, "cropbox", page.rect)
                        crop_W = crop_box.width
                        crop_H = crop_box.height
                        if w_cx < 0.03 * crop_W or w_cx > 0.97 * crop_W or w_cy < 0.03 * crop_H or w_cy > 0.97 * crop_H:
                            logger.info(f"CV Detector: Skipping margin word '{w[4]}' at ({w_cx:.1f}, {w_cy:.1f})")
                            continue
                        
                        # Skip if the match falls inside a masked schedule table area (unless attached to genuine door opening geometry)
                        is_inside_table = False
                        for tr in table_rects:
                            if w_cx >= tr.x0 and w_cx <= tr.x1 and w_cy >= tr.y0 and w_cy <= tr.y1:
                                is_inside_table = True
                                break
                        
                        # Validate opening vector geometry (Criterion A: swing arcs, Criterion B: cased jamb lines, Criterion C: callout symbol)
                        has_vector_geometry, n_line_segments, max_l_len, n_curve_segments, max_c_len = validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0, return_details=True, drawings=drawings_on_page)
                        
                        # If text is inside table area and has NO door vector geometry, skip it (table cell)
                        if is_inside_table and not has_vector_geometry:
                            continue
                            
                        import fitz as fz
                        inst_rect = fz.Rect(w[0], w[1], w[2], w[3])
                        search_rect = inst_rect + (-70, -70, 70, 70)
                        nearby_drawings = [
                            d for d in drawings_on_page
                            if d.get("rect") and fz.Rect(d["rect"]).intersects(search_rect)
                        ]
                        
                        # Count nearby arc curves (both Bezier and polyline-chain arcs)
                        arc_paths = []
                        poly_arcs = find_polyline_chain_arcs(nearby_drawings, (w_cx, w_cy), radius=50.0)
                        for arc in poly_arcs:
                            arc_cx, arc_cy = arc["center"]
                            dist = ((arc_cx - w_cx) ** 2 + (arc_cy - w_cy) ** 2) ** 0.5
                            if dist <= 50:
                                arc_paths.append(arc)

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
                            "arc_count": len(arc_paths),
                            "has_vector_geometry": has_vector_geometry
                        })
                        
                # Construct 2D Concave Outer Hull Polygon using Shapely (if available)
                wall_lines = []
                exterior_boundary = None
                
                if SHAPELY_AVAILABLE:
                    page_w, page_h = page.rect.width, page.rect.height
                    for d in drawings_on_page:
                        r_val = d.get("rect")
                        if not r_val: continue
                        r = fz.Rect(r_val)
                        if r.width > page_w * 0.75 or r.height > page_h * 0.75: continue
                        if r.width < 2 and r.height < 2: continue
                        
                        width = d.get("width") or 0.0
                        items = d.get("items", [])
                        has_curve = any(it[0] in ("c", "v", "y") for it in items)
                        if has_curve: continue
                        
                        if width >= 0.7 or d.get("fill") is not None or (r.width > 25 and r.height > 25):
                            wall_lines.append(LineString([(r.x0, r.y0), (r.x1, r.y1)]))

                    if wall_lines:
                        try:
                            buffered_walls = [line.buffer(8.0) for line in wall_lines]
                            building_polygon = unary_union(buffered_walls)
                            main_poly = max(building_polygon.geoms, key=lambda p: p.area) if isinstance(building_polygon, MultiPolygon) else building_polygon
                            exterior_boundary = main_poly.exterior
                            logger.info(f"Shapely Hull: Built 2D perimeter polyline length={exterior_boundary.length:.1f} from {len(wall_lines)} CAD wall segments.")
                        except Exception as poly_err:
                            logger.error(f"Shapely Hull: Failed to construct building polygon: {poly_err}")
                            exterior_boundary = None
                else:
                    logger.warning("Shapely engine disabled (SHAPELY_AVAILABLE=False). All detections will be flagged for review.")

                for word_text, matches in candidates_by_mark.items():
                    # STEP 2 Occurrence-Count-Based Gating Algorithm
                    filtered_matches = []
                    for m in matches:
                        w = m["word"]
                        inst_rect = m["inst_rect"]
                        
                        # Room Tag Pre-Filter (Drop Sub-Pattern 2A and Sub-Pattern 2B)
                        is_combined_room = is_combined_room_name_and_mark(w, words_on_page)
                        is_area_block = is_room_container_area_block(inst_rect, words_on_page)
                        
                        if is_combined_room or is_area_block:
                            logger.info(f"CV Detector Pre-Filter: Dropped candidate '{word_text}' at ({m['w_cx']:.1f}, {m['w_cy']:.1f}) (Room Tag Pre-Filter: combined={is_combined_room}, area_block={is_area_block})")
                            continue
                        filtered_matches.append(m)
                        
                    N_rem = len(filtered_matches)
                    valid_matches_for_mark = []
                    
                    if N_rem == 1:
                        # RULE 1: Single occurrence remaining after room-tag pre-filter -> Treat as genuine door mark immediately for LOCATION!
                        m = filtered_matches[0]
                        inst_rect = m["inst_rect"]
                        m["min_arc_dist"] = compute_min_dist_to_door_arc(m["w_cx"], m["w_cy"], drawings_on_page)
                        m["is_attached"] = is_tag_attached_to_door_opening(inst_rect, drawings_on_page)
                        m["is_anchor_dot"] = is_hinge_anchor_dot_connected(inst_rect, drawings_on_page, r_min=1.0, r_max=4.0)
                        m["is_cased_jamb"] = detect_wall_endcap_jamb_signature(inst_rect, drawings_on_page)
                        m["is_inside_tag_circle"] = is_enclosed_in_tag_circle(m["w_cx"], m["w_cy"], m["nearby_drawings"])
                        m["is_stacked"] = is_stacked_door_callout(m["word"], words_on_page)
                        m["is_touching_arc"] = m["min_arc_dist"] <= 35.0
                        
                        is_genuine_geom = (
                            m.get("has_vector_geometry", False) or 
                            m["is_attached"] or 
                            m["is_touching_arc"] or 
                            m["is_inside_tag_circle"] or 
                            m["is_anchor_dot"] or 
                            m["is_cased_jamb"] or 
                            m["is_stacked"]
                        )
                        m["has_highlight"] = is_genuine_geom
                        valid_matches_for_mark = [m]
                        logger.info(f"CV Detector Rule 1: Single occurrence for mark '{word_text}' at ({m['w_cx']:.1f}, {m['w_cy']:.1f}) -> Location resolved (has_highlight={is_genuine_geom})")
                        
                    elif N_rem > 1:
                        # RULE 3: Multiple occurrences remaining -> Run full geometry validation pipeline to disambiguate
                        for m in filtered_matches:
                            inst_rect = m["inst_rect"]
                            m["min_arc_dist"] = compute_min_dist_to_door_arc(m["w_cx"], m["w_cy"], drawings_on_page)
                            m["is_attached"] = is_tag_attached_to_door_opening(inst_rect, drawings_on_page)
                            m["is_anchor_dot"] = is_hinge_anchor_dot_connected(inst_rect, drawings_on_page, r_min=1.0, r_max=4.0)
                            m["is_cased_jamb"] = detect_wall_endcap_jamb_signature(inst_rect, drawings_on_page)
                            m["is_inside_tag_circle"] = is_enclosed_in_tag_circle(m["w_cx"], m["w_cy"], m["nearby_drawings"])
                            m["is_stacked"] = is_stacked_door_callout(m["word"], words_on_page)
                            m["is_touching_arc"] = m["min_arc_dist"] <= 35.0
                            
                            is_genuine_geom = (
                                m.get("has_vector_geometry", False) or 
                                m["is_attached"] or 
                                m["is_touching_arc"] or 
                                m["is_inside_tag_circle"] or 
                                m["is_anchor_dot"] or 
                                m["is_cased_jamb"] or 
                                m["is_stacked"]
                            )
                            m["has_highlight"] = is_genuine_geom
                            if is_genuine_geom:
                                valid_matches_for_mark.append(m)
                            else:
                                logger.info(f"CV Detector Rule 3: Dropped candidate '{word_text}' at ({m['w_cx']:.1f}, {m['w_cy']:.1f}) (Multi-occurrence geometry validation failed)")
                                
                        if not valid_matches_for_mark:
                            best_m = min(filtered_matches, key=lambda x: x.get("min_arc_dist", 999.0))
                            best_m["has_highlight"] = False
                            valid_matches_for_mark = [best_m]
                    else:
                        # N_rem == 0: Fallback if all matches were room tags
                        if word_text in sched_marks and matches:
                            best_m = min(matches, key=lambda x: compute_min_dist_to_door_arc(x["w_cx"], x["w_cy"], drawings_on_page))
                            best_m["has_highlight"] = False
                            valid_matches_for_mark = [best_m]

                    # STEP 4 Multi-Match Preservation: Deduplicate spatially (within 8pt) but preserve distinct physical door matches
                    final_matches = []
                    for m in valid_matches_for_mark:
                        if any(abs(fm["w_cx"] - m["w_cx"]) < 8.0 and abs(fm["w_cy"] - m["w_cy"]) < 8.0 for fm in final_matches):
                            continue
                        final_matches.append(m)
                        
                    for m in final_matches:
                        w = m["word"]
                        w_x, w_y = m["w_x"], m["w_y"]
                        w_cx, w_cy = m["w_cx"], m["w_cy"]
                        inst_rect = m["inst_rect"]
                        nearby_drawings = m["nearby_drawings"]
                        
                        # 3-Zone Geometry Engine Evaluation via Shapely Boundary Polyline
                        dist_to_boundary = 999.0
                        host_dist = 999.0
                        is_borderline = False
                        is_perimeter = False
                        
                        if exterior_boundary:
                            dist_to_boundary = exterior_boundary.distance(Point(w_cx, w_cy))
                            nearby_walls = [l for l in wall_lines if l.distance(Point(w_cx, w_cy)) <= 80.0]
                            if nearby_walls:
                                best_wall = min(nearby_walls, key=lambda l: exterior_boundary.distance(l))
                                host_dist = exterior_boundary.distance(best_wall)
                            else:
                                host_dist = dist_to_boundary
                                
                            if dist_to_boundary <= 25.0:
                                is_perimeter = True
                                is_borderline = False
                            elif 25.0 < dist_to_boundary <= 85.0:
                                is_perimeter = True
                                is_borderline = True
                            else:
                                is_perimeter = False
                                is_borderline = False
                        else:
                            # Geometry engine unavailable -> force borderline review safety net!
                            is_perimeter = True
                            is_borderline = True

                        logger.info(f"CV Detector DEBUG: MATCH FOUND word={word_text!r} at ({w_cx:.1f},{w_cy:.1f}), dist_to_boundary={dist_to_boundary:.1f}pt, host_dist={host_dist:.1f}pt, is_borderline={is_borderline}")
                        
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
                        
                        # Crop-quality guardrail: reject crops with no nearby wall lines/drawings in vector page
                        if len(drawings_on_page) > 0 and not nearby_drawings:
                            logger.info(f"VLM Guardrails: Rejecting empty vector crop for mark {word_text} (no drawings near tag)")
                            detections.append({
                                "mark": word_text,
                                "location": "Unknown",
                                "opening_mode": "UNKNOWN",
                                "int_ext": "Exterior" if is_perimeter else "Interior",
                                "floor_no": str(floor_no),
                                "floor_name": floor_name,
                                "page_no": str(page_idx),
                                "w_cx": w_cx,
                                "w_cy": w_cy,
                                "bbox": [inst_rect.x0, inst_rect.y0, inst_rect.x1, inst_rect.y1]
                            })
                            continue

                        # Solution 1: Expand crop radius to 80pt to capture room labels in high resolution,
                        # centered exactly on the door mark
                        clip_rect = inst_rect + (-80, -80, 80, 80)
                        try:
                            pix = page.get_pixmap(clip=clip_rect, dpi=200)
                            import re, uuid
                            
                            clean_mark_file = re.sub(r'[^a-zA-Z0-9_-]', '_', word_text)
                            crop_filename = f"crop_f{floor_no}_p{page_idx}_{clean_mark_file}_{w_idx}_{uuid.uuid4().hex[:6]}.png"
                            crop_path = os.path.join(settings.OUTPUT_DIR, crop_filename)
                            pix.save(crop_path)
                            
                            all_temp_crops.append(crop_path)
                            
                            # Queue LLM task for location and classification mapping
                            location_tasks.append((word_text, floor_no, floor_name, crop_path, opening_mode, is_perimeter, w_cx, w_cy, [inst_rect.x0, inst_rect.y0, inst_rect.x1, inst_rect.y1], page_idx, dist_to_boundary, host_dist, is_borderline))
                        except Exception as crop_err:
                            logger.error(f"Failed to create crop for mark {word_text}: {crop_err}")
                            # Still record the programmatic result without location
                            detections.append({
                                "mark": word_text,
                                "location": "",
                                "opening_mode": opening_mode,
                                "int_ext": "Exterior" if is_perimeter else "Interior",
                                "dist_to_boundary": dist_to_boundary,
                                "host_dist": host_dist,
                                "is_borderline": is_borderline,
                                "floor_no": str(floor_no),
                                "floor_name": floor_name,
                                "page_no": str(page_idx),
                                "w_cx": w_cx,
                                "w_cy": w_cy,
                                "bbox": [inst_rect.x0, inst_rect.y0, inst_rect.x1, inst_rect.y1]
                            })
                            
            doc.close()

        # Run location LLM tasks concurrently
        logger.info(f"CV Detector: Running {len(location_tasks)} location-detection LLM tasks...")
        
        async def run_location_task(mark, floor_no, floor_name, crop_path, programmatic_mode, is_perimeter, w_cx, w_cy, bbox, page_idx, dist_to_boundary, host_dist, is_borderline):
            vlm_res = await classify_door_crop_vlm(crop_path, mark, floor_no, semaphore)
            
            vlm_mode = vlm_res.get("matched_code", "UNKNOWN")
            # Programmatic mode (CAD vector swing arcs & schedule facts) is PRIMARY physical signal.
            # VLM vision guess is only fallback if programmatic mode is UNKNOWN.
            opening_mode = programmatic_mode if programmatic_mode != "UNKNOWN" else (vlm_mode if vlm_mode != "UNKNOWN" else "SGL")
            
            vlm_wall = vlm_res.get("wall_type", "UNKNOWN")
            
            # STEP 1 & 2 Rule: 2D Building Geometry is PRIMARY physical signal. Geometry beats vision.
            # Doors deep inside building footprint (dist_to_boundary > 85.0 pt) are deterministically Interior.
            if dist_to_boundary > 85.0:
                int_ext = "Interior"
                logger.info(f"CV Detector INT/EXT: Mark '{mark}' at ({w_cx:.1f},{w_cy:.1f}) is deep inside footprint (dist={dist_to_boundary:.1f}pt > 85pt) -> Classified INTERIOR by 2D Geometry (VLM wall guess '{vlm_wall}' bypassed).")
            # Perimeter Zone (dist_to_boundary <= 85.0 pt): VLM tiebreaker invoked only in perimeter zone
            elif vlm_wall in ["EXT", "EXTERIOR"]:
                int_ext = "Exterior"
                logger.info(f"CV Detector INT/EXT: Mark '{mark}' in perimeter zone (dist={dist_to_boundary:.1f}pt <= 85pt) with VLM wall guess '{vlm_wall}' -> Classified EXTERIOR tiebreaker.")
            else:
                int_ext = "Interior"
                
            sched_item = sched_items_by_mark.get(mark) or {}
            l1_mode = classify_opening_from_schedule(sched_item)
            l2_mode = programmatic_mode
            l3_mode = vlm_mode

            return {
                "mark": mark,
                "location": vlm_res.get("location", "Unknown"),
                "layer1_schedule_mode": l1_mode,
                "layer2_vector_mode": l2_mode,
                "layer3_vlm_mode": l3_mode,
                "opening_mode": opening_mode,
                "int_ext": int_ext,
                "dist_to_boundary": dist_to_boundary,
                "host_dist": host_dist,
                "is_borderline": is_borderline,
                "vlm_opening_mode": vlm_mode,
                "vlm_wall_type": vlm_wall,
                "vlm_confidence": vlm_res.get("confidence", "low"),
                "vlm_reasoning": f"2D Geometry Primary Signal (dist={dist_to_boundary:.1f}pt, host_dist={host_dist:.1f}pt, is_borderline={is_borderline}). VLM wall type guess: {vlm_wall}",
                "floor_no": str(floor_no),
                "floor_name": floor_name,
                "page_no": str(page_idx),
                "w_cx": w_cx,
                "w_cy": w_cy,
                "bbox": bbox
            }
        
        # Strict Sequential Batching (B=3): Execute 1 batch of 3 requests, await full completion before proceeding to next batch
        BATCH_SIZE = 3
        location_results = []
        total_batches = (len(location_tasks) + BATCH_SIZE - 1) // BATCH_SIZE if location_tasks else 0
        
        for batch_idx, i in enumerate(range(0, len(location_tasks), BATCH_SIZE), 1):
            batch = location_tasks[i:i + BATCH_SIZE]
            logger.info(f"CV Detector VLM: Dispatching Batch {batch_idx}/{total_batches} ({len(batch)} requests)...")
            b_res = await asyncio.gather(
                *[run_location_task(m, f, fn, cp, om, ip, cx, cy, box, p_idx, db, hd, ib) for m, f, fn, cp, om, ip, cx, cy, box, p_idx, db, hd, ib in batch]
            )
            location_results.extend(b_res)
            logger.info(f"CV Detector VLM: Batch {batch_idx}/{total_batches} fulfilled successfully ({len(b_res)} responses).")
            if i + BATCH_SIZE < len(location_tasks):
                await asyncio.sleep(0.5)
                
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
                
        # Log OpenRouter API rate-limit run metrics
        vlm_metrics = openrouter_client.get_metrics_summary()
        logger.info(
            f"CV Detector: Completed. Found and classified {len(detections)} marks on drawings. "
            f"OpenRouter VLM API Metrics: {vlm_metrics}"
        )
        return {"cv_results": {"detections": detections, "vlm_metrics": vlm_metrics}}

        
    except Exception as e:
        logger.critical(f"CV Detector overall failure: {e}", exc_info=True)
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
        return {"cv_results": {"detections": [], "error": str(e)}}
