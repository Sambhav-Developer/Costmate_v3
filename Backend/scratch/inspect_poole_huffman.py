import fitz
import os

plan_a_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
plan_b_path = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")
sched_a_path = os.path.abspath("../Assets/POOLE HUFFMAN/Schedule_A.pdf")
sched_b_path = os.path.abspath("../Assets/POOLE HUFFMAN/Schedule_B.pdf")

print("=== PLAN A TEXT SAMPLES ===")
doc = fitz.open(plan_a_path)
page = doc[0]
rect = page.rect
print(f"Page rect: {rect}")
text_words = page.get_text("words")
print(f"Total words on Plan A: {len(text_words)}")
# Print words that look like tags or numbers or room names
for w in text_words:
    # w is (x0, y0, x1, y1, word, block_no, line_no, word_no)
    txt = w[4]
    if len(txt) <= 8 and (any(c.isdigit() for c in txt) or txt in ["CORR", "STO", "BEV", "STA", "ROOM"]):
        print(f"Word '{txt}' at box ({w[0]:.1f}, {w[1]:.1f}, {w[2]:.1f}, {w[3]:.1f})")

print("\n=== PLAN B TEXT SAMPLES ===")
doc_b = fitz.open(plan_b_path)
page_b = doc_b[0]
print(f"Page rect: {page_b.rect}")
words_b = page_b.get_text("words")
print(f"Total words on Plan B: {len(words_b)}")
for w in words_b:
    txt = w[4]
    if len(txt) <= 8 and (any(c.isdigit() for c in txt) or txt in ["CORR", "STO", "BEV", "STA", "ROOM"]):
        print(f"Word '{txt}' at box ({w[0]:.1f}, {w[1]:.1f}, {w[2]:.1f}, {w[3]:.1f})")

print("\n=== SCHEDULE A TEXT SAMPLES ===")
doc_sa = fitz.open(sched_a_path)
for i, p in enumerate(doc_sa):
    print(f"Schedule A Page {i+1} text sample:\n{p.get_text('text')[:400]}")

print("\n=== SCHEDULE B TEXT SAMPLES ===")
doc_sb = fitz.open(sched_b_path)
for i, p in enumerate(doc_sb):
    print(f"Schedule B Page {i+1} text sample:\n{p.get_text('text')[:400]}")
