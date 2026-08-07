"""Test with larger search radius."""
import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
words = page.get_text("words")
drawings = page.get_drawings()

RADIUS = 150  # Try larger radius

for w in words:
    wt = w[4].strip(".,()[]{}-_#*").upper()
    if wt not in {"RS034"}:
        continue
    
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    mark_cx = (mark_rect.x0 + mark_rect.x1) / 2
    mark_cy = (mark_rect.y0 + mark_rect.y1) / 2
    search_rect = mark_rect + (-RADIUS,-RADIUS,RADIUS,RADIUS)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    print(f"RS034 with radius={RADIUS}: {len(nearby)} nearby")
    
    curve_arcs = []
    for d in nearby:
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if not has_curve:
            continue
        
        r = fitz.Rect(d.get("rect"))
        cx = (r.x0 + r.x1) / 2
        cy = (r.y0 + r.y1) / 2
        dist = ((cx-mark_cx)**2 + (cy-mark_cy)**2)**0.5
        w_size = r.width
        h_size = r.height
        area = w_size * h_size
        aspect = max(w_size,h_size) / max(min(w_size,h_size), 0.1)
        fill = d.get("fill")
        dashes = d.get("dashes")
        dtype = d.get("type")
        
        print(f"  ARC: dist={dist:.0f} w={w_size:.0f} h={h_size:.0f} area={area:.0f} aspect={aspect:.1f} fill={fill} dashes={dashes!r} type={dtype}")
        print(f"       rect={r}")
        curve_arcs.append((dist, w_size, h_size, area, aspect, fill, dashes, r))

doc.close()
