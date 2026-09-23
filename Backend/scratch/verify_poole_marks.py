import fitz
import os

plan_a = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
plan_b = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")

target_marks = ["94", "98A", "98B", "99A", "105", "71", "72", "77", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14"]

for name, pth in [("Original_Plan_A.pdf", plan_a), ("Original_Plan_B.pdf", plan_b)]:
    doc = fitz.open(pth)
    page = doc[0]
    words = page.get_text("words")
    word_texts = [w[4].strip(".,()[]{}-_#*").upper() for w in words]
    print(f"\n=== {name} ===")
    for tm in target_marks:
        if tm in word_texts:
            count = word_texts.count(tm)
            print(f"  Mark '{tm}': FOUND on drawing ({count} occurrences)")
        else:
            print(f"  Mark '{tm}': NOT FOUND on drawing")
