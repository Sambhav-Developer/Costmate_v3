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
    search_rect = mark_rect + (-80,-80,80,80)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    print(f"RS034: mark_cx={mark_cx:.1f} mark_cy={mark_cy:.1f}, {len(nearby)} nearby drawings")
    
    for i, d in enumerate(nearby):
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if not has_curve:
            continue
        
        arc_rect = fitz.Rect(d.get("rect"))
        arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
        arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
        dist = ((arc_cx - mark_cx)**2 + (arc_cy - mark_cy)**2)**0.5
        
        dashes = d.get("dashes", None)
        fill = d.get("fill")
        dtype = d.get("type")
        
        print(f"  CURVE [{i}]: dist={dist:.1f} fill={fill} dashes={dashes!r} type={dtype} rect={arc_rect}")
        
        if dist < 20:
            print(f"    -> SKIP (bubble)")
            continue
        
        # Check dashes
        is_dashed = False
        if dashes is not None:
            if isinstance(dashes, str):
                clean = dashes.strip()
                if clean and clean not in ("[] 0", "[] 0.0", "[]"):
                    is_dashed = True
            elif isinstance(dashes, (list, tuple)) and len(dashes) > 0:
                is_dashed = True
        
        print(f"    -> ACCEPTED as door arc! is_dashed={is_dashed}")

doc.close()
