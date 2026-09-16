import fitz
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    validate_vector_opening_geometry,
    reassemble_pdf_words
)

pdf_path = os.path.abspath("../Assets/FIRST BAPTIS HIGH SCHOOL/Original_Plan.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
words_on_page = reassemble_pdf_words(page.get_text("words"))

schedule_marks = ["100A", "101A", "102A", "103A", "104A", "104B", "105A", "105B", "106A", "107A", "107B", 
                  "110A", "110B", "110C", "111A", "112A", "113A", "114A", "115A", "116A", "117A", "118A", "121A"]

print(f"Total words on page: {len(words_on_page)}")

found_count = 0
valid_count = 0

for w in words_on_page:
    txt = w[4].strip(".,()[]{}-_#*").upper()
    if txt in schedule_marks:
        found_count += 1
        w_cx = (w[0] + w[2]) / 2.0
        w_cy = (w[1] + w[3]) / 2.0
        is_valid = validate_vector_opening_geometry(page, (w_cx, w_cy), radius=60.0)
        if is_valid:
            valid_count += 1
        print(f"Mark '{txt:5s}' at ({w_cx:6.1f}, {w_cy:6.1f}) | validate_vector_opening_geometry = {is_valid}")

print(f"\nSummary: Found text for {found_count}/{len(schedule_marks)} marks. Vector geometry valid for {valid_count}/{found_count}.")
