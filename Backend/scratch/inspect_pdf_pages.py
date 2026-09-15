import fitz
import os

pdf_path = os.path.abspath("../Assets/FIRST BAPTIS HIGH SCHOOL/Original_Plan.pdf")
doc = fitz.open(pdf_path)
print(f"Original_Plan.pdf has {len(doc)} pages:")
for i, page in enumerate(doc):
    text = page.get_text()
    print(f"  Page {i}: {len(text)} chars | Preview: {repr(text[:100])}")
    # Search for mark 101A or 102A on this page
    words = [w[4] for w in page.get_text("words")]
    found_marks = [m for m in ["100A", "101A", "102A", "105A", "107A", "110A"] if m in words]
    print(f"    Page {i} contains schedule marks: {found_marks}")
