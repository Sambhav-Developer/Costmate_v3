"""Final validation of classify_opening_from_drawings with 120pt radius."""
import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
words = page.get_text("words")
drawings = page.get_drawings()

RADIUS = 120

def classify_opening_from_drawings(drawings_near, mark_rect):
    mark_cx = (mark_rect.x0 + mark_rect.x1) / 2
    mark_cy = (mark_rect.y0 + mark_rect.y1) / 2

    arc_paths = []
    for d in drawings_near:
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if not has_curve:
            continue

        dashes = d.get("dashes", None)
        arc_rect = fitz.Rect(d.get("rect"))
        arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
        arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
        dist = ((arc_cx - mark_cx) ** 2 + (arc_cy - mark_cy) ** 2) ** 0.5

        is_dashed = False
        if dashes is not None:
            if isinstance(dashes, str):
                clean = dashes.strip()
                if clean and clean not in ("[] 0", "[] 0.0", "[]"):
                    is_dashed = True
            elif isinstance(dashes, (list, tuple)) and len(dashes) > 0:
                is_dashed = True

        arc_area = arc_rect.width * arc_rect.height
        if dist < 15 and arc_area < 200:
            continue  # label bubble

        arc_paths.append({"rect": arc_rect, "cx": arc_cx, "cy": arc_cy, "dist": dist, "is_dashed": is_dashed})

    if not arc_paths:
        return "SGL"

    if any(a["is_dashed"] for a in arc_paths):
        return "DA"

    def centroid_dist(a, b):
        return ((a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2) ** 0.5

    groups = []
    for arc in arc_paths:
        placed = False
        for g in groups:
            if any(centroid_dist(arc, existing) < 60 for existing in g):
                g.append(arc)
                placed = True
                break
        if not placed:
            groups.append([arc])

    return "CO" if len(groups) >= 2 else "SGL"


TEST_MARKS = {
    "RS023": "SGL",
    "RS034": "CO",
    "RS038": "SGL",
}

for w in words:
    wt = w[4].strip(".,()[]{}-_#*").upper()
    if wt not in TEST_MARKS:
        continue
    
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    search_rect = mark_rect + (-RADIUS,-RADIUS,RADIUS,RADIUS)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    result = classify_opening_from_drawings(nearby, mark_rect)
    expected = TEST_MARKS[wt]
    status = "[OK]" if result == expected else "[FAIL]"
    print(f"{status} {wt}: got={result!r} expected={expected!r} ({len(nearby)} drawings in radius)")

doc.close()
