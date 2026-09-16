import fitz
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    validate_vector_opening_geometry,
    reassemble_pdf_words,
    safe_extract_curve_points,
    safe_extract_line_points
)

pdf_path = os.path.abspath("../Assets/FIRST BAPTIS HIGH SCHOOL/Original_Plan.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
words_on_page = reassemble_pdf_words(page.get_text("words"))
drawings = page.get_drawings()

target_marks = ["100A", "101A", "102A", "103A", "104A", "104B", "105A", "105B", "106A", "107A", "107B", 
                "110A", "110B", "110C", "111A", "112A", "113A", "114A", "115A", "116A", "117A", "118A", "121A"]

print(f"Total drawings on page: {len(drawings)}")

for w in words_on_page:
    txt = w[4].strip(".,()[]{}-_#*").upper()
    if txt in target_marks:
        w_cx = (w[0] + w[2]) / 2.0
        w_cy = (w[1] + w[3]) / 2.0
        
        search_rect = fitz.Rect(w_cx - 60, w_cy - 60, w_cx + 60, w_cy + 60)
        nearby_drawings = [d for d in drawings if fitz.Rect(d["rect"]).intersects(search_rect)]
        
        curves = 0
        lines = 0
        rect_callouts = 0
        
        for d in nearby_drawings:
            p_rect = fitz.Rect(d["rect"])
            w_d, h_d = p_rect.width, p_rect.height
            if 8.0 <= w_d <= 80.0 and 8.0 <= h_d <= 80.0:
                rect_callouts += 1
            for item in d.get("items", []):
                cmd = item[0]
                if cmd in ("c", "v", "y", "qu"):
                    curves += 1
                elif cmd == "l":
                    lines += 1
                    
        is_valid = validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0)
        print(f"Mark '{txt:5s}' at ({w_cx:6.1f}, {w_cy:6.1f}) -> valid={str(is_valid):5s} | nearby_drawings={len(nearby_drawings):2d}, curves={curves:2d}, lines={lines:2d}, rect_callouts={rect_callouts:2d}")
