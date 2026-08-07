"""Debug RS023 with 120pt radius."""
import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
words = page.get_text("words")
drawings = page.get_drawings()

RADIUS = 120

for w in words:
    wt = w[4].strip(".,()[]{}-_#*").upper()
    if wt != "RS023":
        continue
    
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    mark_cx = (mark_rect.x0 + mark_rect.x1) / 2
    mark_cy = (mark_rect.y0 + mark_rect.y1) / 2
    search_rect = mark_rect + (-RADIUS,-RADIUS,RADIUS,RADIUS)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    print(f"RS023 mark center: ({mark_cx:.0f}, {mark_cy:.0f}), {len(nearby)} nearby")
    
    for d in nearby:
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if not has_curve:
            continue
        
        arc_rect = fitz.Rect(d.get("rect"))
        cx = (arc_rect.x0 + arc_rect.x1) / 2
        cy = (arc_rect.y0 + arc_rect.y1) / 2
        dist = ((cx - mark_cx)**2 + (cy - mark_cy)**2)**0.5
        dashes = d.get("dashes")
        fill = d.get("fill")
        is_dashed = False
        if dashes is not None:
            if isinstance(dashes, str) and dashes.strip() not in ("[] 0", "[] 0.0", "[]", ""):
                is_dashed = True
        
        print(f"  ARC: dist={dist:.0f} cx={cx:.0f} cy={cy:.0f} fill={fill} dashes={dashes!r} is_dashed={is_dashed} w={arc_rect.width:.0f} h={arc_rect.height:.0f}")

doc.close()
