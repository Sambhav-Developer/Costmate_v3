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
                    raise ValueError(f"Failed to download drawing {file_source}: {dl_err}")
            else:
                local_raw_path = file_source
                if not os.path.exists(local_raw_path):
                    logger.warning(f"Local drawing path does not exist: {local_raw_path}")
                    raise ValueError(f"Local drawing path does not exist: {local_raw_path}")
                    
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
                raise ValueError(f"Failed to open drawing {local_raw_path}: {open_err}")
                
            highlighted_count = 0
            
            for page_num, page in enumerate(doc):
                effective_floor_idx = page_num if len(raw_drawings) == 1 and len(doc) > 1 else idx
                current_floor_no = effective_floor_idx + 1
                
                page_dets = [d for d in detections if str(d.get("floor_no")) == str(current_floor_no) and str(d.get("page_no", "0")) == str(page_num)]
                for d in page_dets:
                    bbox = d.get("bbox")
                    if not bbox:
                        continue
                        
                    total_detections_with_bbox += 1
                    
                    mark = str(d.get("mark", "")).strip().upper()
                    sched_info = sched_lookup.get(mark, {})
                    
                    # Fallback lookup for bifurcated marks (e.g. D -> D.1, D.2 or D1 -> D1.1)
                    if not sched_info:
                        for k, item_data in sched_lookup.items():
                            orig_tag = str(item_data.get("original_tag", "")).strip().upper()
                            if orig_tag == mark or k.startswith(f"{mark}."):
                                sched_info = item_data
                                break
                    
                    # Case-insensitive material column lookup
                    material = ""
                    # 5 SKILL.md Color Standard definitions (RGB normalized 0-1 for fitz)
                    # 🟡 Yellow (#FFFF00, RGB 255, 255, 0): Interior opening
                    color_interior = (1.0, 1.0, 0.0)
                    # 🔵 Cyan/Blue (#00B0F0 / #007FFF): Exterior opening
                    color_exterior = (0.0, 0.498, 1.0)
                    # 🟢 Green (#92D050, RGB 146, 208, 80): Garage / parking / soft exterior
                    color_soft_ext = (0.57, 0.815, 0.314)
                    # 🟠 Orange (#FFC000, RGB 255, 192, 0): Window, sidelite, borrowed lite
                    color_window   = (1.0, 0.75, 0.0)
                    # 🩷 Pink (#FF69B4 / #FF00FF): Not in scope / Storefront
                    color_storefront = (1.0, 0.0, 1.0)

                    # Determine classification status for highlight color branching
                    raw_mode = str(sched_info.get("_reconciled_opening_mode") or sched_info.get("OPENING MODE") or "").strip().upper()
                    raw_ie = str(sched_info.get("_reconciled_int_ext") or sched_info.get("INT/EXT") or "").strip().upper()
                    wall_rating = str(sched_info.get("WALL RATING") or sched_info.get("FIRE RATING") or sched_info.get("WALL TYPE") or sched_info.get("RATING") or sched_info.get("COMMENTS") or "").strip().upper()
                    
                    if raw_ie == "NOT IN SCOPE" or sched_info.get("excluded") or raw_mode == "STOREFRONT" or "STOREFRONT" in wall_rating or "BARRIER" in wall_rating:
                        highlight_color = color_storefront # Pink #FF69B4 / #FF00FF
                    elif raw_ie == "SOFT EXTERIOR" or any(g_kw in wall_rating for g_kw in ["GARAGE", "PARKING", "BREEZEWAY", "COMPACTOR", "CELLAR"]):
                        highlight_color = color_soft_ext # Green #92D050 (Garage / parking / soft exterior)
                    elif raw_ie in ["WINDOW", "SIDELITE", "BORROWED LITE"] or any(w_kw in wall_rating for w_kw in ["WINDOW", "SIDELITE", "BORROWED LITE", "TRANSOM"]):
                        highlight_color = color_window # Orange #FFC000 (Window, sidelite, borrowed lite)
                    elif any(x in raw_ie for x in ["EXT", "EXTERNAL", "EXTERIOR"]) or "EXTERIOR" in wall_rating or "PARTITION" in wall_rating:
                        highlight_color = color_exterior # Blue / Cyan
                    else:
                        highlight_color = color_interior # Yellow #FFFF00 (Interior)

                        
                    inst_rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                    annot = page.add_highlight_annot(inst_rect)
                    annot.set_colors(stroke=highlight_color)
                    annot.update()
                    highlighted_count += 1
                    total_highlighted += 1
                    
            # Add SKILL.md Section 25 Per-Floor Legend Overlay Box
            for page in doc:
                try:
                    legend_rect = fitz.Rect(30, page.rect.height - 130, 260, page.rect.height - 30)
                    page.draw_rect(legend_rect, color=(0, 0, 0), fill=(0.95, 0.95, 0.95), width=1)
                    page.insert_text(fitz.Point(40, page.rect.height - 115), "OPENING TAKEOFF LEGEND", fontsize=9, fontname="helv", color=(0,0,0))
                    page.insert_text(fitz.Point(40, page.rect.height - 100), "YELLOW: Interior Doors (#FFFF00)", fontsize=8, fontname="helv", color=(0.8, 0.8, 0.0))
                    page.insert_text(fitz.Point(40, page.rect.height - 87),  "BLUE: Exterior Doors (#007FFF)", fontsize=8, fontname="helv", color=(0.0, 0.498, 1.0))
                    page.insert_text(fitz.Point(40, page.rect.height - 74),  "PINK: Storefront / Not in Scope (#FF00FF)", fontsize=8, fontname="helv", color=(1.0, 0.0, 1.0))
                    page.insert_text(fitz.Point(40, page.rect.height - 61),  "GREEN: Garage / Soft Exterior (#92D050)", fontsize=8, fontname="helv", color=(0.3, 0.6, 0.1))
                    page.insert_text(fitz.Point(40, page.rect.height - 48),  "ORANGE: Window / Sidelite (#FFC000)", fontsize=8, fontname="helv", color=(1.0, 0.5, 0.0))
                except Exception as leg_err:
                    logger.warning(f"Failed to draw legend overlay box: {leg_err}")

            logger.info(f"Highlighted {highlighted_count} items on drawing {idx} ({os.path.basename(local_raw_path)})")
            master_doc.insert_pdf(doc)
            doc.close()
            
        # Save the master consolidated PDF with SKILL.md Section 33 Filename
        import datetime
        proj_title = state.get("project_name") or "Costmate_Takeoff"
        clean_proj_name = "".join(c for c in proj_title if c.isalnum() or c in [' ', '_', '-']).strip().replace(' ', '_')
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        file_name = f"{clean_proj_name}_Division8_Takeoff_MarkedUp_{today_str}.pdf"
        
        out_path = os.path.join(settings.OUTPUT_DIR, file_name)
        if master_doc.page_count > 0:
            master_doc.save(out_path)
        else:
            raise ValueError("Consolidated PDF has zero pages. No drawings were annotated.")
        master_doc.close()
        logger.info(f"Consolidated annotated PDF successfully saved at {out_path}")
        
        missing_coords_count = len(detections) - total_highlighted
        logger.info(f"Self-Check: Total Detections = {len(detections)}, Detections with bbox = {total_detections_with_bbox}, Highlighted = {total_highlighted}")
        
        if total_highlighted != len(detections):
            msg = f"Self-Check FAILED: count(highlighted_items)={total_highlighted} does not match count(detections)={len(detections)} (missing {missing_coords_count} highlights)."
            logger.error(msg)
            for d in detections:
                if not d.get("bbox"):
                    unannotated_marks.append(d.get("mark"))
            raise ValueError(f"{msg} Unannotated marks: {unannotated_marks}")
            
        from app.core.cloud import upload_to_cloudinary
        cloud_url = upload_to_cloudinary(out_path, resource_type="raw") or out_path
        
        if cloud_url != out_path and os.path.exists(out_path):
            # We will no longer delete the local file so you have a local copy as well
            logger.info(f"Keeping local file: {out_path}")
                
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
