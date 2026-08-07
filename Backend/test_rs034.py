import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
for page_idx, page in enumerate(doc):
    words = page.get_text('words')
    drawings = page.get_drawings()
    print(f'Page {page_idx}: {len(words)} words, {len(drawings)} drawings')
    for w in words:
        wt = w[4].strip('.,()[]{}-_#*').upper()
        if wt in {'RS034', 'RS023', 'RS038'}:
            print(f'  FOUND: {wt} at {w[0]:.1f},{w[1]:.1f}')
            mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
            search_rect = mark_rect + (-80,-80,80,80)
            nearby = [d for d in drawings if d.get('rect') and fitz.Rect(d['rect']).intersects(search_rect)]
            for d in nearby:
                items = d.get('items', [])
                has_curve = any(it[0] in ('c','qu') for it in items)
                if has_curve:
                    dash_val = repr(d.get('dashes'))
                    print(f'    ARC: dashes={dash_val} type={d.get("type")} rect={d.get("rect")}')
doc.close()
print('DONE')
