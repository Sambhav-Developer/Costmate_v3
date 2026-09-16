import fitz
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

plan_a = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
plan_b = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")

doc_a = fitz.open(plan_a)
page_a = doc_a[0]

doc_b = fitz.open(plan_b)
page_b = doc_b[0]

# Mark 94 on Plan A
w_94 = (826.7, 988.5)
rect_94 = fitz.Rect(w_94[0]-40, w_94[1]-40, w_94[0]+40, w_94[1]+40)
drawings_94 = [d for d in page_a.get_drawings() if fitz.Rect(d["rect"]).intersects(rect_94)]
print(f"=== Mark '94' on Plan A at {w_94} ===")
print(f"Nearby drawings count: {len(drawings_94)}")
for d in drawings_94:
    for item in d.get("items", []):
        cmd = item[0]
        if cmd == "l":
            p1, p2 = item[1], item[2]
            length = ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
            print(f"  Line segment: p1=({p1.x:.1f},{p1.y:.1f}), p2=({p2.x:.1f},{p2.y:.1f}) len={length:.1f}pt")
        elif cmd in ["c", "v", "y"]:
            p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
            chord = ((p1.x - p4.x)**2 + (p1.y - p4.y)**2)**0.5
            print(f"  Bezier curve chord: {chord:.1f}pt")

# Mark 71, 72, 77 on Plan B
for mark, loc in [("71", (1300.8, 1292.5)), ("72", (1300.8, 1252.9)), ("77", (1363.3, 978.6))]:
    rect = fitz.Rect(loc[0]-40, loc[1]-40, loc[0]+40, loc[1]+40)
    drawings = [d for d in page_b.get_drawings() if fitz.Rect(d["rect"]).intersects(rect)]
    print(f"\n=== Mark '{mark}' on Plan B at {loc} ===")
    print(f"Nearby drawings count: {len(drawings)}")
    for d in drawings:
        for item in d.get("items", []):
            cmd = item[0]
            if cmd == "l":
                p1, p2 = item[1], item[2]
                length = ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
                print(f"  Line segment: p1=({p1.x:.1f},{p1.y:.1f}), p2=({p2.x:.1f},{p2.y:.1f}) len={length:.1f}pt")
            elif cmd in ["c", "v", "y"]:
                p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                chord = ((p1.x - p4.x)**2 + (p1.y - p4.y)**2)**0.5
                print(f"  Bezier curve chord: {chord:.1f}pt")
