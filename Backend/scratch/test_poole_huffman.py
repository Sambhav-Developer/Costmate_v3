import os
import sys
import fitz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    validate_vector_opening_geometry,
    reassemble_pdf_words,
    find_closest_schedule_mark,
    is_room_container_area_block,
    is_combined_room_name_and_mark
)

assets_dir = os.path.abspath("../Assets/POOLE HUFFMAN")
plan_a_path = os.path.join(assets_dir, "Original_Plan_A.pdf")
plan_b_path = os.path.join(assets_dir, "Original_Plan_B.pdf")

# Poole Huffman schedule marks are not present in uploaded schedule PDFs, so sched_marks = set()
sched_marks = set()

for p_name, p_path in [("Plan A", plan_a_path), ("Plan B", plan_b_path)]:
    if not os.path.exists(p_path):
        continue
    doc = fitz.open(p_path)
    page = doc[0]
    words = reassemble_pdf_words(page.get_text("words"))
    
    discovered_marks = []
    for w in words:
        raw_word = w[4].strip(".,()[]{}-_#*").upper()
        
        matched_mark = find_closest_schedule_mark(raw_word, sched_marks)
        if not matched_mark and 1 <= len(raw_word) <= 8 and (raw_word.isalnum() or "-" in raw_word):
            if not is_combined_room_name_and_mark(w, words) and not is_room_container_area_block((w[0], w[1], w[2], w[3]), words):
                w_cx = (w[0] + w[2]) / 2.0
                w_cy = (w[1] + w[3]) / 2.0
                if validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0):
                    matched_mark = raw_word
                    
        if matched_mark:
            w_cx = (w[0] + w[2]) / 2.0
            w_cy = (w[1] + w[3]) / 2.0
            discovered_marks.append((matched_mark, round(w_cx, 1), round(w_cy, 1)))
            
    print(f"\n================ {p_name} ================")
    print(f"Discovered {len(discovered_marks)} door marks on floor plan:")
    for m in discovered_marks:
        print(f"  Mark '{m[0]:8s}' at ({m[1]:6.1f}, {m[2]:6.1f})")
