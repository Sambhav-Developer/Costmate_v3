import pdfplumber

pdf_path = r"c:\Users\Hp\Desktop\Costmate_v3\Assets\Morgan Stanley\Level 20.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    left, top, right, bottom = 719.4, 169.0, 1692.4, 756.0
    cropped = page.crop((left, top, right, bottom), relative=True)
    
    words = cropped.extract_words()
    # Group words into lines
    lines = []
    for w in words:
        found = False
        for line in lines:
            if abs(line[0]['top'] - w['top']) < 3:
                line.append(w)
                found = True
                break
        if not found:
            lines.append([w])
            
    for line in lines:
        line.sort(key=lambda w: w['x0'])
    lines.sort(key=lambda l: l[0]['top'])
    
    print("\n--- ALL WORDS ROW-BY-ROW INSIDE THE CROP BOX ---")
    for idx, line in enumerate(lines):
        text = " | ".join([f"x0={w['x0']:.1f}:{w['text']}" for w in line])
        print(f"Row {idx} (top={line[0]['top']:.1f}): {text}")
