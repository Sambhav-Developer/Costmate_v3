import fitz

PDF_PATH = r'C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf'
doc = fitz.open(PDF_PATH)
page = doc[0]
drawings = page.get_drawings()

# Inspect RS023 closely - show ALL nearby drawings including those with dashes
words = page.get_text('words')
for w in words:
    wt = w[4].strip('.,()[]{}-_#*').upper()
    if wt != 'RS023':
        continue
    print(f'RS023 at ({w[0]:.1f},{w[1]:.1f},{w[2]:.1f},{w[3]:.1f})')
    mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
    # Larger search area
    search_rect = mark_rect + (-120,-120,120,120)
    nearby = [d for d in drawings if d.get('rect') and fitz.Rect(d['rect']).intersects(search_rect)]
    print(f'Total drawings in wider search: {len(nearby)}')
    for i, d in enumerate(nearby):
        items = d.get('items', [])
        has_curve = any(it[0] in ('c','qu') for it in items)
        dashes = d.get('dashes')
        dtype = d.get('type')
        color = d.get('color')
        fill = d.get('fill')
        width = d.get('width')
        print(f'  [{i}] type={dtype} dashes={dashes!r} color={color} fill={fill} width={width} has_curve={has_curve} rect={d.get("rect")}')
        if has_curve:
            print(f'       *** ARC DETECTED ***')
            for j, it in enumerate(items):
                print(f'          item[{j}]: {it}')

doc.close()
print('DONE')
