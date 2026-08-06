import os
import json
import asyncio
import traceback
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.services.graph.state import CostmateState
from app.core.logging import logger
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
    if block_no < 0 or block_no >= len(blocks):
        return False
    try:
        b = blocks[block_no]
        block_text = b[4].lower()
        words = [w.strip(".,()[]{}-_#*") for w in block_text.split()]
        if len(words) > 1:
            if any(kw in words for kw in ROOM_KEYWORDS):
                return True
        return False
    except:
        return False

async def analyze_crop(crop_path: str, mark: str, floor_no: int, semaphore: asyncio.Semaphore) -> dict:
    """Sends a cropped image around a door mark to LLM to extract context."""
    async with semaphore:
        prompt = f"""
        Analyze this cropped image around a door or window mark '{mark}' on a floor plan drawing for Floor {floor_no}.
        Look at the symbol next to the highlighted mark:
        1. location: Identify the name of the room or corridor the door/window belongs to. Look at room labels in or next to the space (e.g. "Shared Office", "Secure Holding Rm 1", "Staff Toilet").
        2. opening_mode: Classify the door/window swing leaf mode:
           - If it is a normal door or has a single-leaf 180 degree continuous arc swing -> "Single"
           - If it is a 180 degree double-acting swing door (continuous or dashed swing on both sides) -> "DA"
           - If it is a double-leaf / two-leaf door -> "CO"
           - If it is a window -> "Fixed" or "Casement"
        3. int_ext: Analyze if it is placed in an interior partition wall ("Interior") or an exterior facade wall ("Exterior").

        Return ONLY a raw JSON block in this structure:
        {{
            "location": "room_name",
            "opening_mode": "Single/DA/CO/Fixed",
            "int_ext": "Interior/Exterior"
        }}
        """
        try:
            res = await openrouter_client.generate_chat(prompt=prompt, image_paths=[crop_path], json_mode=True, temperature=0.1)
            data = parse_json_response(res)
            return {
                "mark": mark,
                "location": data.get("location", ""),
                "opening_mode": data.get("opening_mode", "Single"),
                "int_ext": data.get("int_ext", "Interior"),
                "floor_no": str(floor_no)
            }
        except Exception as e:
            logger.error(f"Error classifying crop for mark {mark} on Floor {floor_no}: {e}")
            return {
                "mark": mark,
                "location": "",
                "opening_mode": "Single",
                "int_ext": "Interior",
                "floor_no": str(floor_no)
            }

async def cv_detector_node(state: CostmateState) -> dict:
    logger.info("CV Detector: Starting crop-based door & window analysis node...")
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed. Cannot run crop analysis.")
        return {"cv_results": {"detections": []}}

    # Gather all raw drawing paths/URLs
    raw_drawings = []
    intake = state.get("intake_data") or {}
    floors = intake.get("floors", [])
    logger.info(f"CV Detector DEBUG: intake floors count={len(floors) if floors else 0}")
    if isinstance(floors, list):
        for i, floor in enumerate(floors):
            raw_url = floor.get("rawUrl")
            page_urls = floor.get("pageUrls", [])
            logger.info(f"CV Detector DEBUG: floor[{i}] rawUrl={raw_url!r}, pageUrls count={len(page_urls)}")
            if raw_url and raw_url not in raw_drawings:
                raw_drawings.append(raw_url)
                
    if not raw_drawings:
        overall_file = state.get("uploaded_file_path")
        logger.info(f"CV Detector DEBUG: No rawUrls found in floors. Fallback uploaded_file_path={overall_file!r}")
        if overall_file:
            raw_drawings.append(overall_file)
            
    logger.info(f"CV Detector DEBUG: raw_drawings to process: {raw_drawings}")
    if not raw_drawings:
        logger.warning("No floor plan drawings found to analyze.")
        return {"cv_results": {"detections": []}}
        
    # Get master schedule items to know which marks to look for
    qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
    doors = qa.get("doors") or []
    windows = qa.get("windows") or []
    items = doors + windows
    
    if not items:
        # Fall back to parsed schedule data from schedule_parser_node
        items = state.get("schedule_data") or []
        
    logger.info(f"CV Detector DEBUG: total schedule items={len(items)}")
    if items:
        sample = items[:3]
        for s in sample:
            logger.info(f"CV Detector DEBUG: sample item keys={list(s.keys())}, mark={s.get('mark','')!r}, type={s.get('type','')!r}")
    if not items:
        logger.warning("No schedule items found in state to locate.")
        return {"cv_results": {"detections": []}}

    sched_marks = set()
    for item in items:
        mark_val = item.get("type") or item.get("mark")
        if mark_val:
            sched_marks.add(str(mark_val).strip().upper())

    downloaded_temps = []
    crop_tasks = []
    all_temp_crops = []
    
    # Global concurrency semaphore for LLM vision crops
    semaphore = asyncio.Semaphore(8)
    
    try:
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        
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
                        
                    temp_local_file = os.path.join(settings.OUTPUT_DIR, f"temp_cv_{idx}_{state.get('session_id', 'temp')}{ext}")
                    logger.info(f"Downloading CV drawing {idx}: {file_source} -> {temp_local_file}")
                    
                    req = urllib.request.Request(file_source, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response, open(temp_local_file, 'wb') as out_file:
                        out_file.write(response.read())
                    local_raw_path = temp_local_file
                    downloaded_temps.append(temp_local_file)
                except Exception as dl_err:
                    logger.error(f"Failed to download drawing {idx}: {dl_err}")
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
                    img_doc = fitz.open(local_raw_path)
                    pdf_bytes = img_doc.convert_to_pdf()
                    doc = fitz.open("pdf", pdf_bytes)
                    img_doc.close()
                else:
                    doc = fitz.open(local_raw_path)
            except Exception as open_err:
                logger.error(f"Failed to open drawing {local_raw_path}: {open_err}")
                continue
                
            # Scan pages for schedule marks and generate crops
            for page_idx, page in enumerate(doc):
                blocks = page.get_text("blocks")
                words_on_page = page.get_text("words")
                logger.info(f"CV Detector DEBUG: floor[{idx}] page[{page_idx}] has {len(words_on_page)} words, looking for {len(sched_marks)} marks")
                logger.info(f"CV Detector DEBUG: sched_marks sample={list(sched_marks)[:10]}")
                
                word_indices = {}
                for w in words_on_page:
                    word_text = w[4].strip(".,()[]{}-_#*").upper()
                    
                    if word_text in sched_marks:
                        logger.info(f"CV Detector DEBUG: MATCH FOUND word={word_text!r} at ({w[0]:.1f},{w[1]:.1f})")
                        # Skip room label blocks
                        block_no = w[5]
                        if is_block_room_label(blocks, block_no, word_text):
                            logger.info(f"CV Detector DEBUG: Skipping {word_text!r} — room label")
                            continue
                            
                        # Increment index of this word on the page for unique crop filename
                        word_indices[word_text] = word_indices.get(word_text, 0) + 1
                        w_idx = word_indices[word_text]
                        
                        # Bounding box of the mark word
                        import fitz as fz
                        inst_rect = fz.Rect(w[0], w[1], w[2], w[3])
                        
                        # Add a 100 points padding (approx 2.5 inches in PDF scale) around the word callout
                        clip_rect = inst_rect + (-100, -100, 100, 100)
                        
                        try:
                            # Render crop as PNG
                            pix = page.get_pixmap(clip=clip_rect, dpi=150)
                            crop_filename = f"crop_floor{floor_no}_page{page_idx}_{word_text}_{w_idx}.png"
                            crop_path = os.path.join(settings.OUTPUT_DIR, crop_filename)
                            pix.save(crop_path)
                            all_temp_crops.append(crop_path)
                            
                            # Queue LLM vision analysis task
                            task = analyze_crop(crop_path, word_text, floor_no, semaphore)
                            crop_tasks.append(task)
                        except Exception as crop_err:
                            logger.error(f"Failed to create crop for mark {word_text}: {crop_err}")
                            
            doc.close()

        # Run all classifications concurrently
        logger.info(f"CV Detector: Spawning {len(crop_tasks)} concurrent crop classifications...")
        detections = await asyncio.gather(*crop_tasks)
        
        # Cleanup temporary raw downloads
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
                
        # Cleanup temporary crop images
        for crop_file in all_temp_crops:
            if os.path.exists(crop_file):
                try: os.remove(crop_file)
                except: pass
                
        logger.info(f"CV Detector: Completed. Found and classified {len(detections)} marks on drawings.")
        return {"cv_results": {"detections": detections}}
        
    except Exception as e:
        logger.error(f"CV Detector overall failure: {e}")
        traceback.print_exc()
        # Clean up all temp files
        for temp_file in downloaded_temps:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
        for crop_file in all_temp_crops:
            if os.path.exists(crop_file):
                try: os.remove(crop_file)
                except: pass
        return {"cv_results": {"detections": []}}
