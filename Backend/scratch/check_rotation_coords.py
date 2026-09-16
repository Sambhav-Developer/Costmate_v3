import fitz
import os

plan_a_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
doc = fitz.open(plan_a_path)
page = doc[0]

print(f"page.rotation = {page.rotation}")
print(f"page.rect = {page.rect}")
print(f"page.cropbox = {page.cropbox}")
print(f"page.mediabox = {page.mediabox}")

# Check words with get_text("words") vs page.get_text("words", sort=False)
words = page.get_text("words")
for w in words:
    if w[4] in ["R5", "R6", "R7", "R12", "R14"]:
        print(f"Word '{w[4]}': box=({w[0]:.1f}, {w[1]:.1f}, {w[2]:.1f}, {w[3]:.1f})")

# Check drawings (vector shapes)
drawings = page.get_drawings()
print(f"Total drawings: {len(drawings)}")
for d in drawings[:5]:
    print(f"Drawing rect: {d['rect']}")
