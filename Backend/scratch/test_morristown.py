import os
import sys
import fitz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    reassemble_pdf_words,
    find_closest_schedule_mark
)

plans_dir = os.path.abspath("../Assets/Morristown/Floor_Plans")
sched_marks = {"94", "98A", "98B", "98C", "99A", "100B", "105", "71", "72", "73", "76", "77", "90", "97"}

for p_file in sorted(os.listdir(plans_dir)):
    if not p_file.endswith(".pdf"):
        continue
    pdf_path = os.path.join(plans_dir, p_file)
    doc = fitz.open(pdf_path)
    page = doc[0]
    words = reassemble_pdf_words(page.get_text("words"))
    
    found = []
    for w in words:
        raw_word = w[4].strip(".,()[]{}-_#*").upper()
        matched = find_closest_schedule_mark(raw_word, sched_marks)
        if matched:
            found.append((matched, round((w[0]+w[2])/2.0, 1), round((w[1]+w[3])/2.0, 1)))
            
    if found:
        print(f"Sheet '{p_file:15s}': Found {len(found)} marks -> {found}")
