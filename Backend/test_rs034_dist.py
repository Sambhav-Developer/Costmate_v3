import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
words = page.get_text("words")
drawings = page.get_drawings()

for w in words:
    wt = w[4].strip(".,()[]{}-_#*").upper()
    if wt != "RS034":
        continue
    
    print(f"RS034 word bbox: x0={w[0]:.1f} y0={w[1]:.1f} x1={w[2]:.1f} y1={w[3]:.1f}")
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    mark_cx = (mark_rect.x0 + mark_rect.x1) / 2
    mark_cy = (mark_rect.y0 + mark_rect.y1) / 2
    print(f"Mark center: ({mark_cx:.1f}, {mark_cy:.1f})")
    
    search_rect = mark_rect + (-80,-80,80,80)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    for i, d in enumerate(nearby):
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if has_curve:
            r = fitz.Rect(d.get("rect"))
            cx = (r.x0 + r.x1) / 2
            cy = (r.y0 + r.y1) / 2
            dist = ((cx - mark_cx)**2 + (cy - mark_cy)**2)**0.5
            print(f"  ARC [{i}]: center=({cx:.1f},{cy:.1f}) dist={dist:.1f} fill={d.get('fill')} rect={r}")

doc.close()
