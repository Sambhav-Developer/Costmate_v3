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
    "shared", "hvac", "elevator", "utility", "laundry", "nourse", "care", "station"
}

def is_block_room_label(blocks, block_no, clean_mark) -> bool:
    """
    Returns True if the block corresponding to the block_no is a room name label.
    """
    if block_no < 0 or block_no >= len(blocks):
        return False
    try:
        b = blocks[block_no]
        block_text = b[4].lower()
        words = [w.strip(".,()[]{}-_#*") for w in block_text.split()]
        # If there are multiple words, check if it's a room label containing typical room name keywords
        if len(words) > 1:
            if any(kw in words for kw in ROOM_KEYWORDS):
                logger.info(f"Skipping room label block [{block_no}]: '{b[4].strip()}' for mark '{clean_mark}'")
                return True
        return False
    except Exception as e:
        logger.warning(f"Error checking block room label: {e}")
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
            
            # Run text highlighting using exact word token matching
            for page in doc:
                blocks = page.get_text("blocks")
                words_on_page = page.get_text("words")
                
                for w in words_on_page:
                    # w format: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                    word_text = w[4].strip(".,()[]{}-_#*").upper()
                    
                    if word_text in sched_lookup:
                        sched_info = sched_lookup[word_text]
                        cv_info = cv_lookup.get(word_text, {})
                        
                        # Case-insensitive material column lookup
                        material = ""
                        for k, v in sched_info.items():
                            if "material" in str(k).lower():
                                material = str(v).upper()
                                break
                        
                        int_ext = str(cv_info.get("int_ext", "")).upper()
                        
                        if any(kw in material for kw in ["ALUMINUM", "GLASS", "ALUMINIUM", "ALUM"]):
                            highlight_color = color_storefront
                        elif int_ext == "EXT":
                            highlight_color = color_exterior
                        else:
                            highlight_color = color_interior
                            
                        # Get bounding box of the word
                        import fitz as fz
                        inst_rect = fz.Rect(w[0], w[1], w[2], w[3])
                        
                        # Smart filter: skip highlighting room name labels
                        block_no = w[5]
                        if is_block_room_label(blocks, block_no, word_text):
                            continue
                            
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
