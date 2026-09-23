import fitz
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    validate_vector_opening_geometry,
    reassemble_pdf_words
)

plan_a_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
plan_b_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")

for name, pth in [("Plan A", plan_a_path), ("Plan B", plan_b_path)]:
    doc = fitz.open(pth)
    page = doc[0]
    words = reassemble_pdf_words(page.get_text("words"))
    print(f"\n================ {name} ================")
    print(f"page.rect={page.rect}, cropbox={page.cropbox}, rotation={page.rotation}")
    
    valid_door_words = []
    for w in words:
        raw_word = w[4].strip(".,()[]{}-_#*").upper()
        if not (1 <= len(raw_word) <= 8):
            continue
        w_cx = (w[0] + w[2]) / 2.0
        w_cy = (w[1] + w[3]) / 2.0
        
        # Validate vector opening geometry
        has_geom, n_lines, max_l, n_curves, max_c = validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0, return_details=True)
        if has_geom:
            valid_door_words.append((raw_word, w_cx, w_cy, n_lines, max_l, n_curves, max_c))
            
    print(f"Found {len(valid_door_words)} text words near door vector geometry:")
    for v in valid_door_words:
        print(f"  Word: '{v[0]:12}' at ({v[1]:.1f}, {v[2]:.1f}) | lines={v[3]} max_l={v[4]:.1f} curves={v[5]} max_c={v[6]:.1f}")
