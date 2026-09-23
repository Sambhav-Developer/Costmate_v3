import fitz
import os
import sys
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    validate_vector_opening_geometry,
    reassemble_pdf_words
)

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
    word_upper = word.upper()
    if word_upper in NON_DOOR_TAG_KEYWORDS:
        return False
    # Filter out scales, quotes, math symbols
    if any(c in word for c in ['"', "'", '=', '/', '\\', '°']):
        return False
    # Filter out detail callouts like I-3.01, A.2, 3.8
    if re.match(r'^[A-Z]?-\d+\.\d+$', word_upper) or re.match(r'^\d+\.\d+$', word_upper):
        return False
    # Single character orphan tags (unless in sched_marks) are usually grid bubbles or noise
    if len(word_upper) == 1 and word_upper not in sched_marks:
        return False
    # Hardware set tags like S1T1
    if re.match(r'^S\d+T\d+$', word_upper):
        return False
    return True

plan_a_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
doc = fitz.open(plan_a_path)
page = doc[0]
words = reassemble_pdf_words(page.get_text("words"))

crop_W = page.cropbox.width
crop_H = page.cropbox.height

candidates = []
for w in words:
    raw_word = w[4].strip(".,()[]{}-_#*").upper()
    if not (1 <= len(raw_word) <= 8):
        continue
    if not is_valid_orphan_tag_candidate(raw_word, set()):
        continue
    w_cx = (w[0] + w[2]) / 2.0
    w_cy = (w[1] + w[3]) / 2.0
    
    # 3% Margin check in unrotated cropbox coordinates
    if w_cx < 0.03 * crop_W or w_cx > 0.97 * crop_W or w_cy < 0.03 * crop_H or w_cy > 0.97 * crop_H:
        continue
        
    has_geom = validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0)
    if has_geom:
        candidates.append((raw_word, w_cx, w_cy))

print(f"\nRefined Candidate Tags ({len(candidates)} total):")
for c in candidates:
    print(f"  Word: '{c[0]:10}' at ({c[1]:.1f}, {c[2]:.1f})")
