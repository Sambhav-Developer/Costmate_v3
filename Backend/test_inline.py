"""Quick direct test of classify_opening_from_drawings for RS034."""
import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
words = page.get_text("words")
drawings = page.get_drawings()

def classify_opening_from_drawings(drawings_near, mark_rect):
    mark_cx = (mark_rect.x0 + mark_rect.x1) / 2
    mark_cy = (mark_rect.y0 + mark_rect.y1) / 2

    arc_groups = []
    for d in drawings_near:
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if not has_curve:
            continue

        dashes = d.get("dashes", None)
        dtype = d.get("type", "")

        arc_rect = fitz.Rect(d.get("rect"))
        arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
        arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
        dist_to_mark = ((arc_cx - mark_cx) ** 2 + (arc_cy - mark_cy) ** 2) ** 0.5
        if dist_to_mark < 20:
            print(f"   SKIP bubble dist={dist_to_mark:.1f}")
            continue

        is_dashed = False
        if dashes is not None:
            if isinstance(dashes, str):
                clean = dashes.strip()
                if clean and clean not in ("[] 0", "[] 0.0", "[]"):
                    is_dashed = True
            elif isinstance(dashes, (list, tuple)) and len(dashes) > 0:
                is_dashed = True

        print(f"   ACCEPTED arc: dist={dist_to_mark:.1f} dashes={dashes!r} is_dashed={is_dashed}")
        arc_groups.append({"rect": arc_rect, "is_dashed": is_dashed, "dashes": dashes, "dtype": dtype})

    print(f"   Total arc_groups: {len(arc_groups)}")
    if not arc_groups:
        return "SGL"

    dashed_arcs = [a for a in arc_groups if a["is_dashed"]]
    if dashed_arcs:
        return "DA"

    solid_arcs = arc_groups
    if len(solid_arcs) == 1:
        return "SGL"

    def x_center(a):
        return (a["rect"].x0 + a["rect"].x1) / 2

    groups = []
    for arc in solid_arcs:
        placed = False
        for g in groups:
            if any(abs(x_center(arc) - x_center(existing)) < 50 for existing in g):
                g.append(arc)
                placed = True
                break
        if not placed:
            groups.append([arc])

    print(f"   Distinct groups: {len(groups)}")
    if len(groups) >= 2:
        return "CO"
    return "SGL"


for w in words:
    wt = w[4].strip(".,()[]{}-_#*").upper()
    if wt not in {"RS023", "RS034", "RS038"}:
        continue
    
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    search_rect = mark_rect + (-80,-80,80,80)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    print(f"\n=== {wt}: {len(nearby)} nearby ===")
    result = classify_opening_from_drawings(nearby, mark_rect)
    print(f"Result: {result}")

doc.close()
