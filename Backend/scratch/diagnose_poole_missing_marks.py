import fitz
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    validate_vector_opening_geometry,
    reassemble_pdf_words,
    is_combined_room_name_and_mark,
    is_room_container_area_block
)

plan_a = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
plan_b = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")

target_marks = ["94", "98A", "98B", "99A", "105", "71", "72", "77"]

for name, pth in [("Original_Plan_A.pdf", plan_a), ("Original_Plan_B.pdf", plan_b)]:
    doc = fitz.open(pth)
    page = doc[0]
    words = reassemble_pdf_words(page.get_text("words"))
    crop_W = page.cropbox.width
    crop_H = page.cropbox.height
    print(f"\n================ {name} ================")
    
    for w in words:
        raw_word = w[4].strip(".,()[]{}-_#*").upper()
        if raw_word in target_marks:
            w_cx = (w[0] + w[2]) / 2.0
            w_cy = (w[1] + w[3]) / 2.0
            margin_ok = (0.03 * crop_W <= w_cx <= 0.97 * crop_W) and (0.03 * crop_H <= w_cy <= 0.97 * crop_H)
            
            is_comb = is_combined_room_name_and_mark(w, words)
            is_room_blk = is_room_container_area_block((w[0], w[1], w[2], w[3]), words)
            has_geom, n_l, max_l, n_c, max_c = validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0, return_details=True)
            
            print(f"Mark '{raw_word}' at box=({w[0]:.1f},{w[1]:.1f},{w[2]:.1f},{w[3]:.1f}) cx={w_cx:.1f} cy={w_cy:.1f}:")
            print(f"  margin_ok={margin_ok} | is_combined_room={is_comb} | is_room_block={is_room_blk}")
            print(f"  has_vector_geometry={has_geom} (lines={n_l} max_l={max_l:.1f}pt curves={n_c} max_c={max_c:.1f}pt)")
