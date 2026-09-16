import fitz
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

plan_a = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
plan_b = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")

def check_leader_or_callout(page, cx, cy, radius=40.0):
    search_rect = fitz.Rect(cx - radius, cy - radius, cx + radius, cy + radius)
    drawings = page.get_drawings()
    
    has_leader = False
    has_callout_bubble = False
    
    for path in drawings:
        p_rect = fitz.Rect(path["rect"])
        if not search_rect.intersects(p_rect):
            continue
            
        items = path.get("items", [])
        
        # Check for leader line (line starting near cx,cy and length >= 15pt)
        for item in items:
            cmd = item[0]
            if cmd == "l":
                p1, p2 = item[1], item[2]
                l_len = ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                d1 = ((p1.x - cx)**2 + (p1.y - cy)**2)**0.5
                d2 = ((p2.x - cx)**2 + (p2.y - cy)**2)**0.5
                # Leader line starts near tag center (d1 <= 35 or d2 <= 35) and extends outwards
                if min(d1, d2) <= 35.0 and l_len >= 15.0:
                    has_leader = True
            elif cmd in ("c", "v", "y"):
                p1 = item[1]
                p4 = item[4]
                c_len = ((p4.x - p1.x)**2 + (p4.y - p1.y)**2)**0.5
                d1 = ((p1.x - cx)**2 + (p1.y - cy)**2)**0.5
                d4 = ((p4.x - cx)**2 + (p4.y - cy)**2)**0.5
                # Callout bubble curve: curve chord 5..35pt near center
                if min(d1, d4) <= 30.0 and 5.0 <= c_len <= 35.0:
                    has_callout_bubble = True

    return has_leader or has_callout_bubble, has_leader, has_callout_bubble

doc_a = fitz.open(plan_a)
page_a = doc_a[0]

doc_b = fitz.open(plan_b)
page_b = doc_b[0]

test_cases = [
    ("94", page_a, (826.7, 988.5)),
    ("98A", page_a, (1069.4, 720.2)),
    ("98B", page_a, (1069.2, 959.3)),
    ("99A", page_a, (1149.0, 959.3)),
    ("105", page_a, (1359.7, 1273.9)),
    ("71", page_b, (1300.8, 1292.5)),
    ("72", page_b, (1300.8, 1252.9)),
    ("77", page_b, (1363.3, 978.6))
]

print("=== LEADER LINE AND CALLOUT BUBBLE TEST ===")
for mark, page, loc in test_cases:
    valid, is_lead, is_bub = check_leader_or_callout(page, loc[0], loc[1])
    print(f"Mark '{mark:4}' at {loc}: valid={valid} (has_leader={is_lead}, has_callout_bubble={is_bub})")
