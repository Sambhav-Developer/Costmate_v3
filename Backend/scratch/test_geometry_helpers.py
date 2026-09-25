import sys
sys.path.insert(0, r'C:\Users\Hp\Desktop\Costmate_v3\Backend')
from app.services.agents.layer2_vision.cv_detector_node import (
    detect_double_egress, detect_bypass, detect_pocket, detect_bifold,
    detect_barn, classify_opening_from_drawings
)
import fitz

mark_cx, mark_cy = 100.0, 100.0

print("=== detect_double_egress ===")
tests = [
    # TRUE DE cases: arcs on opposite sides of wall center
    ('DE horizontal wall (one arc above, one below)',
     [[{'cx': 100, 'cy': 50,  'rect': fitz.Rect(80,30,120,70)}],
      [{'cx': 100, 'cy': 150, 'rect': fitz.Rect(80,130,120,170)}]],
     True),
    ('DE vertical wall (one arc left, one right)',
     [[{'cx': 30,  'cy': 100, 'rect': fitz.Rect(10,80,60,120)}],
      [{'cx': 170, 'cy': 100, 'rect': fitz.Rect(150,80,190,120)}]],
     True),

    # TRUE PR cases: BOTH arcs on the SAME side of wall center (swing into same room)
    ('PR horizontal wall (both arcs ABOVE mark_cy, side-by-side)',
     [[{'cx': 75,  'cy': 60, 'rect': fitz.Rect(50,40,100,80)}],
      [{'cx': 125, 'cy': 60, 'rect': fitz.Rect(100,40,150,80)}]],
     # y_spread=0, x_spread=50 -> x-dominant -> vertical DE check
     # left: 75 < 75 -> NO (not < mark_cx-25=75). right: 125 > 125 -> NO
     # So DE check fails -> returns False. PASS!
     False),
    ('PR vertical wall (both arcs to the RIGHT of mark_cx, up-down)',
     [[{'cx': 150, 'cy': 70, 'rect': fitz.Rect(130,50,170,90)}],
      [{'cx': 150, 'cy': 130,'rect': fitz.Rect(130,110,170,150)}]],
     # y_spread=60, x_spread=0 -> y-dominant -> horizontal DE check
     # above: cy=70 < 75 -> NO. below: cy=130 > 125 -> YES. above is empty -> False
     False),
]

all_pass = True
for name, groups, expected in tests:
    result = detect_double_egress(groups, mark_cx, mark_cy)
    status = 'PASS' if result == expected else 'FAIL'
    if status == 'FAIL': all_pass = False
    print(f'  [{status}] {name}')
    print(f'         got={result}, expected={expected}')

print()
print("=== classify schedule passthrough (8 types) ===")
mark_rect = fitz.Rect(95, 95, 105, 105)
sched_tests = [
    ({'type': 'POCKET DOOR'}, 'PKT'),
    ({'type': 'BARN DOOR'}, 'SLD'),
    ({'type': 'BYPASS'}, 'BYPASS'),
    ({'type': 'BIFOLD'}, 'BIFOLD'),
    ({'type': 'DOUBLE EGRESS'}, 'DE'),
    ({'type': 'UNEQUAL PAIR'}, 'UNEQ'),
    ({'type': 'CASED OPENING'}, 'CO'),
    ({'type': 'DOUBLE ACTING'}, 'DA'),
    ({'type': 'SINGLE'}, 'SGL'),
    ({'type': 'PAIR'}, 'PR'),
]
for item, expected in sched_tests:
    result = classify_opening_from_drawings([], mark_rect, item=item)
    status = 'PASS' if result == expected else 'FAIL'
    if status == 'FAIL': all_pass = False
    print(f'  [{status}] schedule type={item["type"]!r}: got={result}, expected={expected}')

print()
print("=== detect_sidelight_geometry ===")
from app.services.agents.layer2_vision.cv_detector_node import detect_sidelight_geometry
drawings_with_sidelight = [
    {"rect": fitz.Rect(120, 100, 155, 108), "items": [("l", (120,100), (155,100))]}
]
res_sidelite = detect_sidelight_geometry(drawings_with_sidelight, mark_cx=100.0, mark_cy=100.0)
status = 'PASS' if res_sidelite["has_sidelite_geom"] and res_sidelite["sidelight_width_pt"] == 35.0 else 'FAIL'
if status == 'FAIL': all_pass = False
print(f'  [{status}] Sidelight glass frame rect (width=35pt at dist~45pt): got={res_sidelite}')

print()
print("=== detect_transom_geometry & detect_clerestory_geometry ===")
from app.services.agents.layer2_vision.cv_detector_node import detect_transom_geometry, detect_clerestory_geometry
res_tr = detect_transom_geometry([{"rect": fitz.Rect(80, 70, 120, 85), "dashes": "[] 0"}], mark_cx=100.0, mark_cy=100.0)
status_tr = 'PASS' if res_tr["has_transom_geom"] else 'FAIL'
if status_tr == 'FAIL': all_pass = False
print(f'  [{status_tr}] Transom header rect (width=40pt at dist~30pt): got={res_tr}')

res_cl = detect_clerestory_geometry([{"rect": fitz.Rect(70, 40, 130, 55), "items": [("l", (70,40), (130,40))]}], mark_cx=100.0, mark_cy=100.0)
status_cl = 'PASS' if res_cl["has_clerestory_geom"] else 'FAIL'
if status_cl == 'FAIL': all_pass = False
print(f'  [{status_cl}] Clerestory ribbon window (width=60pt at dist~65pt): got={res_cl}')

print()
print('ALL PASS' if all_pass else 'SOME TESTS FAILED')
