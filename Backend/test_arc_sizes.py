import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
drawings = page.get_drawings()
words = page.get_text("words")

for w in words:
    wt = w[4].strip(".,()[]{}-_#*").upper()
    if wt not in {"RS034", "RS023", "RS038"}:
        continue
    
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    search_rect = mark_rect + (-80,-80,80,80)
    nearby = [d for d in drawings if d.get("rect") and fitz.Rect(d["rect"]).intersects(search_rect)]
    
    print(f"\n=== {wt} at {w[0]:.1f},{w[1]:.1f} ===")
    for i, d in enumerate(nearby):
        items = d.get("items", [])
        has_curve = any(it[0] in ("c", "qu") for it in items)
        if has_curve:
            r = fitz.Rect(d.get("rect"))
            w_size = r.width
            h_size = r.height
            area = w_size * h_size
            print(f"  ARC: fill={d.get('fill')!r} w={w_size:.1f} h={h_size:.1f} area={area:.0f} type={d.get('type')}")
            # Mark bubble: small area and one dimension << other
            is_bubble = area < 500 or (w_size > 0 and h_size > 0 and max(w_size/h_size, h_size/w_size) > 5)
            print(f"       is_bubble={is_bubble}")

doc.close()
