import fitz
import os

pdf_path = os.path.abspath("../Assets/Morristown/Door_Schedule.pdf")
if os.path.exists(pdf_path):
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        txt = page.get_text()
        print(f"--- Page {i+1} ---")
        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        print(f"Sample lines: {lines[:30]}")
