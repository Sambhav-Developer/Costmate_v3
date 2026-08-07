import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
drawings = page.get_drawings()
words = page.get_text("words")

for w in words:
    wt = w[4].strip(".,()[]{}-_#*").upper()
    if wt != "RS034":
        continue
    
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    search_rect = mark_rect + (-80,-80,80,80)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    print(f"RS034 at {w[0]:.1f},{w[1]:.1f}")
    print(f"Total nearby: {len(nearby)}")
    for i, d in enumerate(nearby):
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if has_curve:
            print(f"  [{i}] ARC: type={d.get('type')} dashes={d.get('dashes')!r} fill={d.get('fill')} color={d.get('color')} rect={d.get('rect')}")
            print(f"       fill check: fill={d.get('fill')!r} == (0,0,0)? {d.get('fill')==(0.0,0.0,0.0)}")
            print(f"       fill check: fill={d.get('fill')!r} == (1,1,1)? {d.get('fill')==(1.0,1.0,1.0)}")
            
            # Simulate the filter
            fill = d.get("fill", None)
            dtype = d.get("type", "")
            if fill and fill != (0.0, 0.0, 0.0) and fill != (1.0, 1.0, 1.0):
                print(f"       FILTERED (colored fill)")
            elif fill == (1.0, 1.0, 1.0) and dtype == "f":
                print(f"       FILTERED (white fill)")
            else:
                print(f"       PASSES filter")

doc.close()
