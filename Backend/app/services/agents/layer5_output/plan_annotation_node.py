import os
import traceback
import openpyxl
from app.core.logging import logger
from app.services.graph.state import CostmateState
from app.config import settings

def get_item_mark(item):
    for k, v in item.items():
        if str(k).lower().strip() in ["mark", "type", "door mark", "door no", "door no.", "id", "mark / type", "mark/type"]:
            return str(v).strip().upper()
    for k, v in item.items():
        if "mark" in str(k).lower() or "type" in str(k).lower():
            return str(v).strip().upper()
    return None

async def plan_annotation_node(state: CostmateState) -> dict:
    logger.info("Plan Annotation Node: Color-coding door and window marks on floor plan drawings...")
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed. Cannot annotate PDF.")
        return {"current_step": "annotation_failed", "error": "PyMuPDF missing"}
        
    # Gather all raw drawing paths/URLs
    raw_drawings = []
    intake = state.get("intake_data") or {}
    floors = intake.get("floors", [])
    if isinstance(floors, list):
        for floor in floors:
            raw_url = floor.get("rawUrl")
            if raw_url and raw_url not in raw_drawings:
                raw_drawings.append(raw_url)
                
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
        items = state.get("schedule_data", [])
        
    # Extract all marks and map them to their schedule details
    sched_lookup = {}
    if items:
        for item in items:
            mark_val = get_item_mark(item)
            if mark_val:
                sched_lookup[str(mark_val).strip().upper()] = item

    # Get computer vision detections context
    cv_results = state.get("cv_results", {}) or {}
    detections = cv_results.get("detections", []) or []
    
    # Saturated, vibrant color definitions (RGB in 0-1 range for fitz)
    color_interior = (1.0, 1.0, 0.0)    # Bright Yellow (255, 255, 0)
    color_exterior = (0.0, 0.8, 1.0)    # Bright Cyan/Sky Blue (0, 204, 255)
    color_storefront = (1.0, 0.0, 0.5)  # Bright Pink/Magenta (255, 0, 128)
    
    downloaded_temps = []
    total_highlighted = 0
    total_detections_with_bbox = 0
    unannotated_marks = []
    
    try:
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        master_doc = fitz.open()
        
        for idx, file_source in enumerate(raw_drawings):
            temp_local_file = None
            local_raw_path = None
            floor_no = idx + 1
            
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
            
            # Filter detections for this floor
            floor_dets = [d for d in detections if str(d.get("floor_no")) == str(floor_no)]
            
            for page_num, page in enumerate(doc):
                page_dets = [d for d in floor_dets if str(d.get("page_no", "0")) == str(page_num)]
                for d in page_dets:
                    bbox = d.get("bbox")
                    if not bbox:
                        continue
                        
                    total_detections_with_bbox += 1
                    
                    mark = str(d.get("mark", "")).strip().upper()
                    sched_info = sched_lookup.get(mark, {})
                    
                    # Case-insensitive material column lookup
                    material = ""
                    for k, v in sched_info.items():
                        if "material" in str(k).lower():
                            material = str(v).upper()
                            break
                            
                    # Determine classification status for highlight color branching
                    raw_mode = sched_info.get("_reconciled_opening_mode") or sched_info.get("OPENING MODE")
                    raw_ie = str(sched_info.get("_reconciled_int_ext") or sched_info.get("INT/EXT") or "").strip().upper()
                    
                    is_blank_classification = (not raw_mode) or (raw_mode == "UNKNOWN") or (not raw_ie) or (raw_ie in ["UNKNOWN", ""])
                    
                    if is_blank_classification:
                        highlight_color = color_storefront  # Pink/Magenta for blank/storefront/cased openings
                    elif any(x in raw_ie for x in ["EXT", "EXTERNAL", "EXTERIOR"]):
                        highlight_color = color_exterior   # Vivid Azure Blue for exterior
                    else:
                        highlight_color = color_interior   # Saturated Yellow/Gold for interior
                        
                    inst_rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                    annot = page.add_highlight_annot(inst_rect)
                    annot.set_colors(stroke=highlight_color)
                    annot.update()
                    highlighted_count += 1
                    total_highlighted += 1
                    
            logger.info(f"Highlighted {highlighted_count} items on drawing {idx} ({os.path.basename(local_raw_path)})")
            master_doc.insert_pdf(doc)
            doc.close()
            
        # Save the master consolidated PDF
        out_path = os.path.join(settings.OUTPUT_DIR, f"{state.get('session_id', 'output')}_annotated.txt")
        master_doc.save(out_path)
        master_doc.close()
        logger.info(f"Consolidated annotated PDF successfully saved at {out_path}")
        
        # Hard check: count(highlighted_items) == count(quantity_rows/detections)
        # Check if there are any detections that had QTY > 0 but zero coordinates/highlights
        missing_coords_count = len(detections) - total_highlighted
        
        logger.info(f"Self-Check: Total Detections = {len(detections)}, Detections with bbox = {total_detections_with_bbox}, Highlighted = {total_highlighted}")
        
        if total_highlighted != len(detections):
            msg = f"Self-Check FAILED: count(highlighted_items)={total_highlighted} does not match count(detections)={len(detections)} (missing {missing_coords_count} highlights)."
            logger.error(msg)
            # Find which marks missed highlights
            for d in detections:
                if not d.get("bbox"):
                    unannotated_marks.append(d.get("mark"))
            # Raise exception to fail loudly
            raise ValueError(f"{msg} Unannotated marks: {unannotated_marks}")
            
        # Upload generated PDF to Cloudinary
        from app.core.cloud import upload_to_cloudinary
        cloud_url = upload_to_cloudinary(out_path, resource_type="raw") or out_path
        
        # Delete local copy from disk
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except:
                pass
                
        # Cleanup temporary files
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
        return {"annotated_pdf_path": cloud_url}
        
    except Exception as e:
        logger.error(f"Error during PDF annotation: {e}")
        traceback.print_exc()
        # Clean up temp files on error
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
        return {"error": str(e), "needs_review": True}
