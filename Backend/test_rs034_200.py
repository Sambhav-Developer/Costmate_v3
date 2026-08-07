"""Find the actual swing arc for RS034 - look at ALL drawings with curves nearby."""
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
    
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    mark_cx = (mark_rect.x0 + mark_rect.x1) / 2
    mark_cy = (mark_rect.y0 + mark_rect.y1) / 2
    
    # Very large search radius
    search_rect = mark_rect + (-200,-200,200,200)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    print(f"RS034 mark center: ({mark_cx:.0f}, {mark_cy:.0f})")
    print(f"Searching with 200pt radius: {len(nearby)} drawings found")
    
    print("\nAll arc-containing paths:")
    for d in nearby:
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if not has_curve:
            continue
        
        r = fitz.Rect(d.get("rect"))
        cx = (r.x0 + r.x1) / 2
        cy = (r.y0 + r.y1) / 2
        dist = ((cx-mark_cx)**2 + (cy-mark_cy)**2)**0.5
        
        print(f"  dist={dist:.0f} w={r.width:.0f} h={r.height:.0f} area={r.width*r.height:.0f} fill={d.get('fill')} dashes={d.get('dashes')!r} type={d.get('type')} rect={r}")

doc.close()
