"""
Validate the new programmatic opening mode classifier on the actual floor plan PDFs.
Expected results based on original Excel:
  RS023 -> SGL  (single leaf, solid 180-degree arc)
  RS034 -> CO   (double leaf, two arcs)
  RS038 -> SGL  (single leaf)
"""
import sys, os
sys.path.insert(0, r'C:\Users\Hp\Desktop\Costmate_v3\Backend')
import fitz

# Copy the classifier function here for quick standalone test
def classify_opening_from_drawings(drawings_near, mark_rect):
    import fitz as fz

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
        fill = d.get("fill", None)

        arc_rect = fz.Rect(d.get("rect"))

        # Skip the mark label bubble: centered very close to the mark text
        arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
        arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
        dist_to_mark = ((arc_cx - mark_cx) ** 2 + (arc_cy - mark_cy) ** 2) ** 0.5
        if dist_to_mark < 20:
            print(f"   SKIP (bubble): dist={dist_to_mark:.1f}")
            continue

        is_dashed = False
        if dashes is not None:
            if isinstance(dashes, str):
                clean = dashes.strip()
                if clean and clean not in ("[] 0", "[] 0.0", "[]"):
                    is_dashed = True
            elif isinstance(dashes, (list, tuple)) and len(dashes) > 0:
                is_dashed = True

        arc_groups.append({
            "rect": arc_rect,
            "is_dashed": is_dashed,
            "dashes": dashes,
            "dtype": dtype,
        })

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

    distinct_doors = len(groups)
    if distinct_doors >= 2:
        return "CO"
    return "SGL"



TEST_MARKS = {
    "RS023": "SGL",  # Expected from original Excel
    "RS034": "CO",   # Expected from original Excel (double leaf)
    "RS038": "SGL",  # Expected from original Excel
}

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)

print(f"Testing on: {PDF_PATH}")
print("=" * 60)

results = {}
for page_idx, page in enumerate(doc):
    words = page.get_text("words")
    drawings = page.get_drawings()
    
    for w in words:
        wt = w[4].strip(".,()[]{}-_#*").upper()
        if wt not in TEST_MARKS:
            continue
        
        if wt in results:
            continue  # already found
        
        mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
        search_rect = mark_rect + (-80, -80, 80, 80)
        nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
        
        result = classify_opening_from_drawings(nearby, mark_rect)
        expected = TEST_MARKS[wt]
        ok = "[OK]" if result == expected else "[FAIL]"
        print(f"{ok} {wt}: got={result!r}  expected={expected!r}")
        
        # Show arc details
        arc_count = 0
        for d in nearby:
            if any(it[0] in ("c","qu") for it in d.get("items",[])):
                fill = d.get("fill")
                skip = (fill and fill not in ((0,0,0),(1,1,1))) or (fill==(1,1,1) and d.get("type")=="f")
                if not skip:
                    arc_count += 1
                    print(f"   arc: dashes={d.get('dashes')!r} rect={d.get('rect')}")
        print(f"   total qualifying arcs: {arc_count}")
        results[wt] = result

doc.close()

print("=" * 60)
correct = sum(1 for m, r in results.items() if r == TEST_MARKS[m])
print(f"Score: {correct}/{len(TEST_MARKS)} correct")
