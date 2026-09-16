import fitz
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    validate_vector_opening_geometry,
    reassemble_pdf_words
)

plan_a_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
doc = fitz.open(plan_a_path)
page = doc[0]
words = reassemble_pdf_words(page.get_text("words"))

crop_W = page.cropbox.width
crop_H = page.cropbox.height

for w in words:
    raw_word = w[4].strip(".,()[]{}-_#*").upper()
    if any(tag in raw_word for tag in ["R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14"]):
        w_cx = (w[0] + w[2]) / 2.0
        w_cy = (w[1] + w[3]) / 2.0
        margin_ok = (0.03 * crop_W <= w_cx <= 0.97 * crop_W) and (0.03 * crop_H <= w_cy <= 0.97 * crop_H)
        has_geom = validate_vector_opening_geometry(page, (w_cx, w_cy), radius=40.0)
        print(f"Tag '{raw_word}': box=({w[0]:.1f}, {w[1]:.1f}, {w[2]:.1f}, {w[3]:.1f}) cx={w_cx:.1f} cy={w_cy:.1f} | margin_ok={margin_ok} has_geom={has_geom}")
