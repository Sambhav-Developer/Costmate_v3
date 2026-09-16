import fitz
import os

plan_a_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
plan_b_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")

for name, pth in [("Plan A", plan_a_path), ("Plan B", plan_b_path)]:
    doc = fitz.open(pth)
    page = doc[0]
    print(f"=== {name} ===")
    print(f"page.rect: {page.rect}")
    print(f"page.rotation: {page.rotation}")
    print(f"page.derotation_matrix: {page.derotation_matrix}")
    print(f"page.rotation_matrix: {page.rotation_matrix}")
    print(f"page.cropbox: {page.cropbox}")
    print(f"page.mediabox: {page.mediabox}")
    words = page.get_text("words")
    for w in words:
        if any(tag in w[4] for tag in ["R5", "R6", "R12", "R14"]):
            print(f"Word '{w[4]}' raw bbox: ({w[0]:.1f}, {w[1]:.1f}, {w[2]:.1f}, {w[3]:.1f})")
