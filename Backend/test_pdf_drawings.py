"""
Diagnostic: Read PDF drawing paths near door marks using PyMuPDF get_drawings()
This will show us if arcs near marks have dashes or not, and how many curves exist.
"""
import fitz
import sys, os

PDF_PATH = r"C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf"
# Try both plan PDFs
PDF_FILES = [
    r"C:\Users\Hp\Desktop\Costmate_v3\Assets\Area A Plan Highlighted.pdf",
    r"C:\Users\Hp\Desktop\Costmate_v3\Assets\Area B Plan Highlighted.pdf",
]


# Marks to check (from schedule)
TEST_MARKS = {"RS023", "RS034", "RS038"}

def rect_area(r):
    return (r.x1 - r.x0) * (r.y1 - r.y0)

def classify_opening_from_drawings(drawings_near, search_rect):
    """
    Classify a door's opening mode from nearby PDF path drawings.
    Returns: "SGL", "DA", or "CO"
    """
    arc_paths = []  # curved bezier paths (door swings)
    
    for d in drawings_near:
        # Check if this drawing has any curve/bezier items
        has_curve = False
        for item in d.get("items", []):
            if item[0] in ("c", "qu"):  # bezier curve or quadratic
                has_curve = True
                break
        
        if not has_curve:
            continue
            
        # Get dash style
        dashes = d.get("dashes", "")
        dash_phase = d.get("dash_phase", 0)
        
        # A path is dashed if dashes field is non-empty string or non-empty list
        is_dashed = False
        if dashes:
            if isinstance(dashes, str) and dashes.strip() not in ("", "[] 0"):
                is_dashed = True
            elif isinstance(dashes, (list, tuple)) and len(dashes) > 0:
                is_dashed = True
        
        arc_paths.append({
            "rect": d.get("rect"),
            "dashes": dashes,
            "is_dashed": is_dashed,
            "items_count": len(d.get("items", [])),
            "color": d.get("color"),
        })
    
    print(f"\n  Arc paths found near mark: {len(arc_paths)}")
    for a in arc_paths:
        print(f"    - dashes={a['dashes']!r} is_dashed={a['is_dashed']} rect={a['rect']} items={a['items_count']}")
    
    if not arc_paths:
        return "SGL"
    
    # Count dashed vs solid arcs
    dashed_arcs = [a for a in arc_paths if a["is_dashed"]]
    solid_arcs = [a for a in arc_paths if not a["is_dashed"]]
    
    # If 2+ solid arcs meeting (CO), check if they span both sides of mark
    if len(solid_arcs) >= 2:
        return "CO"
    
    # If any dashed arc
    if dashed_arcs:
        return "DA"
    
    # Single solid arc
    return "SGL"


for PDF_PATH in PDF_FILES:
    if not os.path.exists(PDF_PATH):
        print(f"SKIP (not found): {PDF_PATH}")
        continue
    print(f"\n{'='*60}")
    print(f"Opening PDF: {PDF_PATH}")
    doc = fitz.open(PDF_PATH)

    for page_idx, page in enumerate(doc):
        words = page.get_text("words")
        drawings = page.get_drawings()
        
        print(f"\n=== Page {page_idx} has {len(words)} words, {len(drawings)} drawings ===")
        
        for w in words:
            word_text = w[4].strip(".,()[]{}-_#*").upper()
            if word_text not in TEST_MARKS:
                continue
            
            print(f"\n--- Mark: {word_text} at ({w[0]:.1f},{w[1]:.1f},{w[2]:.1f},{w[3]:.1f}) ---")
            
            mark_rect = fitz.Rect(w[0], w[1], w[2], w[3])
            search_rect = mark_rect + (-80, -80, 80, 80)
            
            # Filter drawings that overlap the search area
            nearby = []
            for d in drawings:
                dr = d.get("rect")
                if dr and fitz.Rect(dr).intersects(search_rect):
                    nearby.append(d)
            
            print(f"  Drawings in search rect: {len(nearby)}")
            
            # Print ALL nearby drawings for inspection
            for i, d in enumerate(nearby):
                dashes = d.get("dashes", "")
                items = d.get("items", [])
                has_curve = any(it[0] in ("c", "qu") for it in items)
                print(f"  [{i}] type={d.get('type')} dashes={dashes!r} color={d.get('color')} has_curve={has_curve} rect={d.get('rect')} items={len(items)}")
                for j, it in enumerate(items[:5]):
                    print(f"        item[{j}]: {it[0]}")
            
            result = classify_opening_from_drawings(nearby, search_rect)
            print(f"  => CLASSIFICATION: {result}")

    doc.close()

print("\nDONE.")

