import os
import traceback
from app.core.logging import logger
from app.services.graph.state import CostmateState
from app.config import settings

# Common room keywords to filter out room name labels from door/window callouts
ROOM_KEYWORDS = {
    "room", "rm", "office", "toilet", "staff", "holding", "treatment", "bed", 
    "ex", "existing", "lounge", "lobby", "corridor", "hall", "stair", "storage", 
    "mech", "electrical", "elec", "janitor", "closet", "bath", "shower", "wc", 
    "vestibule", "entry", "exit", "classroom", "kitchen", "conf", "conference", 
    "shared", "hvac", "elevator", "utility", "laundry", "nourse", "care", "station",
    "exam", "examination", "it", "pantry", "waiting", "reception", "soiled", "clean", 
    "nurse", "nook", "dictation", "physician", "touchdown", "med", "meds", "unisex", 
    "vest", "clos", "lrd", "sub", "wait", "consult", "consultation", "work", "lockers", 
    "triage", "harrison", "mamaroneck"
}

def find_closest_schedule_mark(word_text, sched_marks):
    if word_text in sched_marks:
        return word_text
    # Common OCR digit-to-letter confusion fixes
    normalized_variants = []
    # Variant A: replace all '0' and 'O' with 'C' (for 3C03/3C06A type marks read as 3003/3O03)
    v_c = word_text.replace('0', 'C').replace('O', 'C')
    normalized_variants.append(v_c)
    # Variant B: replace 'C' with '0'
    v_0 = word_text.replace('C', '0')
    normalized_variants.append(v_0)
    # Variant C: replace 'O' with '0'
    v_o2 = word_text.replace('O', '0')
    normalized_variants.append(v_o2)
    # Variant D: replace '8' with 'B' or 'B' with '8'
    normalized_variants.append(word_text.replace('8', 'B'))
    normalized_variants.append(word_text.replace('B', '8'))
    
    for v in normalized_variants:
        if v != word_text and v in sched_marks:
            return v
    return None

def get_schedule_table_rects(page):
    import fitz
    rects = []
    for term in ["DOOR AND FRAME SCHEDULE", "DOOR SCHEDULE", "WINDOW SCHEDULE", "FRAME SCHEDULE"]:
        rects_found = page.search_for(term)
        for r in rects_found:
            page_rect = page.rect
            table_rect = fitz.Rect(r.x0 - 20, r.y0 - 50, page_rect.x1, page_rect.y1)
            rects.append(table_rect)
    return rects

def is_block_room_label(blocks, block_no, clean_mark) -> bool:
    if block_no < 0 or block_no >= len(blocks):
        return False
    try:
        b = blocks[block_no]
        block_text = b[4].strip().upper()
        block_words = [w.strip(".,()[]{}-_#*") for w in block_text.split()]
        block_words = [w for w in block_words if w]
        
        words_lower = [w.lower() for w in block_words]
        if any(kw in words_lower for kw in ROOM_KEYWORDS):
            return True
        return False
    except:
        return False

async def plan_annotation_node(state: CostmateState) -> dict:
    logger.info("Plan Annotation Node: Color-coding door and window marks on floor plan drawings...")
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed. Cannot annotate PDF.")
        return {"current_step": "annotation_failed", "error": "PyMuPDF missing"}
        
    # Gather all raw drawing paths/URLs
    raw_drawings = []
    
    # 1. Look for rawUrls in intake_data floor levels
    intake = state.get("intake_data") or {}
    floors = intake.get("floors", [])
    if isinstance(floors, list):
        for floor in floors:
            raw_url = floor.get("rawUrl")
            if raw_url and raw_url not in raw_drawings:
                raw_drawings.append(raw_url)
                
    # 2. Fall back to uploaded_file_path if no floor rawUrls found
    if not raw_drawings:
        overall_file = state.get("uploaded_file_path")
        if overall_file:
            raw_drawings.append(overall_file)
            
    if not raw_drawings:
        logger.warning("No floor plan drawings found to annotate.")
        return {}
        
    logger.info(f"Gathered floor plan files to annotate: {raw_drawings}")
    
    # Get master schedule items (prioritize QA verified, fall back to prefilled)
    qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
    doors = qa.get("doors") or []
    windows = qa.get("windows") or []
    items = doors + windows
    
    if not items:
        logger.warning("No schedule items found to highlight.")
        return {}

    # Extract all marks and map them to their schedule details
    sched_lookup = {}
    for item in items:
        mark_val = item.get("type") or item.get("mark")
        if mark_val:
            sched_lookup[str(mark_val).strip().upper()] = item

    # Get computer vision detections context
    cv_results = state.get("cv_results", {}) or {}
    detections = cv_results.get("detections", []) or []
    cv_lookup = {str(d.get("mark", "")).strip().upper(): d for d in detections if d.get("mark")}
    
    # Saturated, vibrant color definitions (RGB in 0-1 range for fitz)
    color_interior = (1.0, 0.9, 0.0)    # Saturated Yellow/Gold (Interior Door/Window)
    color_exterior = (0.0, 0.45, 1.0)   # Vivid Azure Blue (Exterior Door/Window)
    color_storefront = (1.0, 0.15, 0.6) # Saturated Magenta/Pink (Glass/Storefront Door/Window)
    
    downloaded_temps = []
    
    try:
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
        # Create a master document to hold all annotated drawings merged together
        master_doc = fitz.open()
        
        for idx, file_source in enumerate(raw_drawings):
            temp_local_file = None
            local_raw_path = None
            
            # Download the file if it's hosted in the cloud (Cloudinary URL)
            if file_source.startswith("http://") or file_source.startswith("https://"):
                try:
                    import urllib.request
                    _, ext = os.path.splitext(file_source.split('?')[0])
                    ext = ext.lower()
                    if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
                        ext = ".pdf"
                        
                    temp_local_file = os.path.join(settings.OUTPUT_DIR, f"temp_raw_{idx}_{state.get('session_id', 'temp')}{ext}")
                    logger.info(f"Downloading drawing {idx}: {file_source} -> {temp_local_file}")
                    
                    req = urllib.request.Request(file_source, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response, open(temp_local_file, 'wb') as out_file:
                        out_file.write(response.read())
                    local_raw_path = temp_local_file
                    downloaded_temps.append(temp_local_file)
                except Exception as dl_err:
                    logger.error(f"Failed to download drawing {idx} ({file_source}): {dl_err}")
                    continue
            else:
                local_raw_path = file_source
                if not os.path.exists(local_raw_path):
                    logger.warning(f"Local drawing path does not exist: {local_raw_path}")
                    continue
                    
            # Open/Convert to PDF
            try:
                file_ext = os.path.splitext(local_raw_path)[1].lower()
                if file_ext in [".png", ".jpg", ".jpeg"]:
                    logger.info(f"Converting image {local_raw_path} to PDF format...")
                    img_doc = fitz.open(local_raw_path)
                    pdf_bytes = img_doc.convert_to_pdf()
                    doc = fitz.open("pdf", pdf_bytes)
                    img_doc.close()
                else:
                    doc = fitz.open(local_raw_path)
            except Exception as open_err:
                logger.error(f"Failed to open drawing {local_raw_path}: {open_err}")
                continue
                
            highlighted_count = 0
            
            sched_marks = list(sched_lookup.keys())
            for page in doc:
                blocks = page.get_text("blocks")
                words_on_page = page.get_text("words")
                drawings_on_page = page.get_drawings()
                table_rects = get_schedule_table_rects(page)
                
                # 1. Collect candidates by mark
                candidates_by_mark = {}
                for w in words_on_page:
                    raw_word = w[4].strip(".,()[]{}-_#*").upper()
                    
                    matched_mark = find_closest_schedule_mark(raw_word, sched_marks)
                    if matched_mark:
                        word_text = matched_mark
                        w_x = (w[0] + w[2]) / 2
                        w_y = (w[1] + w[3]) / 2
                        
                        # Skip if the match falls inside a masked schedule table area
                        is_inside_table = False
                        for tr in table_rects:
                            if w_x >= tr.x0 and w_x <= tr.x1 and w_y >= tr.y0 and w_y <= tr.y1:
                                is_inside_table = True
                                break
                        if is_inside_table:
                            continue
                            
                        # Skip if block is room label block
                        block_no = w[5]
                        if is_block_room_label(blocks, block_no, word_text):
                            continue
                            
                        import fitz as fz
                        inst_rect = fz.Rect(w[0], w[1], w[2], w[3])
                        search_rect = inst_rect + (-70, -70, 70, 70)
                        nearby_drawings = [
                            d for d in drawings_on_page
                            if d.get("rect") and fz.Rect(d["rect"]).intersects(search_rect)
                        ]
                        
                        # Count nearby arc curves
                        arc_paths = []
                        for d in nearby_drawings:
                            items = d.get("items", [])
                            has_curve = any(it[0] in ("c", "qu") for it in items)
                            if not has_curve:
                                continue
                            arc_rect = fz.Rect(d.get("rect"))
                            arc_cx = (arc_rect.x0 + arc_rect.x1) / 2
                            arc_cy = (arc_rect.y0 + arc_rect.y1) / 2
                            dist = ((arc_cx - w_x) ** 2 + (arc_cy - w_y) ** 2) ** 0.5
                            if dist <= 50:
                                # Skip tiny label circle arcs
                                arc_area = arc_rect.width * arc_rect.height
                                if dist < 15 and arc_area < 200:
                                    continue
                                arc_paths.append(d)
                                
                        candidates_by_mark.setdefault(word_text, []).append({
                            "word": w,
                            "w_x": w_x,
                            "w_y": w_y,
                            "inst_rect": inst_rect,
                            "arc_count": len(arc_paths)
                        })
                        
                for word_text, matches in candidates_by_mark.items():
                    # Deduplicate: if any match has nearby door arcs, only keep matches that have arcs
                    has_arcs = any(m["arc_count"] > 0 for m in matches)
                    if has_arcs:
                        filtered_matches = [m for m in matches if m["arc_count"] > 0]
                    else:
                        filtered_matches = matches
                        
                    # Also apply simple spatial deduplication: within 60pt
                    final_matches = []
                    for m in filtered_matches:
                        if any(abs(fm["w_x"] - m["w_x"]) < 60 and abs(fm["w_y"] - m["w_y"]) < 60 for fm in final_matches):
                            continue
                        final_matches.append(m)
                        
                    for m in final_matches:
                        w = m["word"]
                        inst_rect = m["inst_rect"]
                        
                        sched_info = sched_lookup[word_text]
                        cv_info = cv_lookup.get(word_text, {})
                        
                        # Case-insensitive material column lookup
                        material = ""
                        for k, v in sched_info.items():
                            if "material" in str(k).lower():
                                material = str(v).upper()
                                break
                        
                        int_ext = str(cv_info.get("int_ext", "")).upper()
                        
                        mat_words = [t.strip() for t in material.split()]
                        if any(kw in material for kw in ["ALUMINUM", "GLASS", "ALUMINIUM", "ALUM", "STOREFRONT"]) or "AL" in mat_words:
                            highlight_color = color_storefront
                        elif int_ext in ["EXT", "EXTERNAL", "EXTERIOR"]:
                            highlight_color = color_exterior
                        else:
                            highlight_color = color_interior
                            
                        annot = page.add_rect_annot(inst_rect)
                        annot.set_colors(stroke=highlight_color, fill=highlight_color)
                        annot.set_opacity(0.65) # Darker opacity for clear visibility
                        annot.update()
                        highlighted_count += 1
                        
            logger.info(f"Highlighted {highlighted_count} items on drawing {idx} ({os.path.basename(local_raw_path)})")
            
            # Merge this annotated drawing into the master document
            master_doc.insert_pdf(doc)
            doc.close()

        # Save the master consolidated PDF
        out_path = os.path.join(settings.OUTPUT_DIR, f"{state.get('session_id', 'output')}_annotated.pdf")
        master_doc.save(out_path)
        master_doc.close()
        
        logger.info(f"Consolidated annotated PDF successfully saved at {out_path}")
        
        # Cleanup temporary files
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete temp file {temp_file}: {cleanup_err}")
                    
        return {"annotated_pdf_path": out_path}
        
    except Exception as e:
        logger.error(f"Error during PDF annotation: {e}")
        traceback.print_exc()
        # Clean up temp files on error
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
        return {"error": str(e)}
