import os
import uuid
import fitz
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from app.config import settings
from app.services.graph.session_manager import session_manager
from app.services.graph.graph import costmate_graph
from app.core.logging import logger
from app.core.exceptions import NotFoundException, ValidationException
from app.modules.estimations.repository import estimation_repo
from app.modules.estimations.schemas import DraftSessionRequest, NotificationRequest

class EstimationService:
    async def upload_floor_plan(self, user_id: int, file) -> dict:
        logger.info(f"Received file upload request: {file.filename}")
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".pdf"]:
            raise ValidationException("Invalid file format. Only PDF, PNG, and JPG/JPEG are supported.")

        session_id = str(uuid.uuid4())
        filename = f"{session_id}{ext}"
        
        try:
            content = await file.read()
            logger.info(f"[{session_id}] File read successfully into memory")
        except Exception as e:
            logger.error(f"Failed to read uploaded file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

        from app.core.cloud import upload_to_cloudinary_bytes
        cloud_file_path = upload_to_cloudinary_bytes(content, filename, resource_type="raw" if ext == ".pdf" else "image")
        active_path = cloud_file_path or "fallback_url"
        active_paths = []
        
        if ext == ".pdf":
            try:
                doc = fitz.open(stream=content, filetype="pdf")
                num_pages = len(doc)
                for page_num in range(num_pages):
                    page = doc.load_page(page_num)
                    width, height = page.rect.width, page.rect.height
                    longest_side = max(width, height)
                    target_pixels = 8000
                    zoom = max(3.5, min(8.0, target_pixels / longest_side))
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    png_filename = f"{session_id}_page{page_num}.png"
                    
                    cloud_png_path = upload_to_cloudinary_bytes(pix.tobytes("png"), png_filename, resource_type="image")
                    if cloud_png_path:
                        active_paths.append(cloud_png_path)
                # Keep active_path as the raw PDF URL instead of overwriting with page0.png
                # active_path = active_paths[0] if active_paths else active_path
            except Exception as e:
                logger.error(f"[{session_id}] Failed to convert PDF pages to images: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to process PDF pages: {str(e)}")
        else:
            active_paths = [active_path]

        session_manager.start_session(session_id, active_path, active_paths, file.filename, user_id)
        return {"session_id": session_id, "filename": file.filename, "status": "processing"}

    def get_user_sessions(self, conn, user_id: int) -> list:
        sessions = []
        rows = estimation_repo.get_user_sessions(conn, user_id)
        for row in rows:
            session_id, state_dict, created_at = row
            if isinstance(state_dict, str):
                state_dict = json.loads(state_dict)
            project_name = state_dict.get("project_name")
            filename = state_dict.get("original_filename")
            if not project_name:
                project_name = filename
            if not project_name:
                uploaded_file = state_dict.get("uploaded_file_path", "")
                project_name = uploaded_file.replace('\\', '/').split('/')[-1] if uploaded_file else "drawing.png"
            status = state_dict.get("status", "processing")
            sessions.append({
                "id": session_id,
                "filename": project_name,
                "original_filename": filename,
                "date": created_at.strftime("%d/%m/%Y") if created_at else "",
                "status": status
            })
        return sessions

    async def get_session_state(self, session_id: str, user_id: int) -> dict:
        restored = await session_manager.restore_session_if_needed(session_id, user_id=user_id)
        if not restored:
            raise NotFoundException("Session not found.")
        
        config = {"configurable": {"thread_id": session_id}}
        state_snapshot = await costmate_graph.aget_state(config)
        if not state_snapshot.values:
            raise NotFoundException("Session not found.")
            
        values = state_snapshot.values
        return {
            "session_id": values.get("session_id"),
            "uploaded_file_path": values.get("uploaded_file_path"),
            "original_filename": values.get("original_filename"),
            "uploaded_page_paths": values.get("uploaded_page_paths", []),
            "project_name": values.get("project_name"),
            "swarm_goal": values.get("swarm_goal"),
            "rate_schedule": values.get("rate_schedule"),
            "status": values.get("status"),
            "current_step": values.get("current_step"),
            "progress_pct": values.get("progress_pct"),
            "qa_prefilled": values.get("qa_prefilled"),
            "qa_verified": values.get("qa_verified"),
            "cv_results": values.get("cv_results"),
            "schedule_data": values.get("schedule_data"),
            "specifications_insights": values.get("specifications_insights"),
            "civil_quantities": values.get("civil_quantities"),
            "steel_quantities": values.get("steel_quantities"),
            "chat_history": values.get("chat_history")
        }

    def create_draft_session(self, conn, user_id: int, req: DraftSessionRequest) -> dict:
        session_id = str(uuid.uuid4())
        estimation_repo.create_draft_session(conn, session_id, user_id, req)
        conn.commit()
        return {"session_id": session_id, "status": "draft"}

    def get_draft_session(self, conn, session_id: str, user_id: int) -> dict:
        row = estimation_repo.get_draft_session(conn, session_id, user_id)
        if not row:
            raise NotFoundException("Draft session not found")
        project_name, swarm_goal, rate_schedule, file_path, original_filename, page_paths, status = row
        return {
            "session_id": session_id,
            "project_name": project_name,
            "swarm_goal": swarm_goal,
            "rate_schedule": rate_schedule,
            "uploaded_file_path": file_path,
            "original_filename": original_filename,
            "uploaded_page_paths": page_paths or [],
            "status": status
        }

    async def upload_draft_file(self, conn, session_id: str, user_id: int, file) -> dict:
        row = estimation_repo.get_draft_session(conn, session_id, user_id)
        if not row:
            raise NotFoundException("Draft session not found")
        project_name = row[0]
        
        logger.info(f"Received draft file upload: {file.filename} for session {session_id}")
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".pdf"]:
            raise ValidationException("Invalid file format. Only PDF, PNG, and JPG/JPEG are supported.")

        filename = f"{session_id}_{uuid.uuid4().hex[:8]}{ext}"
        
        try:
            content = await file.read()
            logger.info(f"[{session_id}] Draft file read successfully into memory")
        except Exception as e:
            logger.error(f"Failed to read draft file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

        from app.core.cloud import upload_to_cloudinary_bytes
        
        cloud_file_path = upload_to_cloudinary_bytes(content, filename, resource_type="raw" if ext == ".pdf" else "image", project_name=project_name)
        active_path = cloud_file_path or "fallback_url"
        active_paths = []

        if ext == ".pdf":
            try:
                doc = fitz.open(stream=content, filetype="pdf")
                num_pages = len(doc)
                for page_num in range(num_pages):
                    page = doc.load_page(page_num)
                    width, height = page.rect.width, page.rect.height
                    longest_side = max(width, height)
                    target_pixels = 8000
                    zoom = max(3.5, min(8.0, target_pixels / longest_side))
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    base_name = os.path.splitext(filename)[0]
                    png_filename = f"{base_name}_page{page_num}.png"
                    
                    cloud_png_path = upload_to_cloudinary_bytes(pix.tobytes("png"), png_filename, resource_type="image", project_name=project_name)
                    if cloud_png_path:
                        active_paths.append(cloud_png_path)
                # Keep active_path as the raw PDF URL instead of overwriting with page0.png
                # active_path = active_paths[0] if active_paths else active_path
            except Exception as e:
                logger.error(f"[{session_id}] Failed to convert PDF pages to images: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to process PDF pages: {str(e)}")
        else:
            active_paths = [active_path]

        estimation_repo.update_draft_session_file(conn, session_id, user_id, active_path, file.filename, active_paths)
        conn.commit()
        return {"session_id": session_id, "filename": file.filename, "status": "file_uploaded", "page_paths": active_paths, "raw_url": active_path}

    async def upload_draft_schedule(self, conn, session_id: str, user_id: int, file) -> dict:
        row = estimation_repo.get_draft_session(conn, session_id, user_id)
        if not row:
            from app.core.exceptions import NotFoundException
            raise NotFoundException("Draft session not found")
        project_name = row[0]
        
        ext = os.path.splitext(file.filename)[1].lower()
        filename = f"{session_id}_schedule{ext}"
        
        try:
            content = await file.read()
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to read schedule file: {str(e)}")

        from app.core.cloud import upload_to_cloudinary_bytes
        
        active_paths = []
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(stream=content, filetype="pdf")
                num_pages = len(doc)
                for page_num in range(num_pages):
                    page = doc.load_page(page_num)
                    width, height = page.rect.width, page.rect.height
                    longest_side = max(width, height)
                    target_pixels = 4000
                    zoom = max(2.0, min(5.0, target_pixels / longest_side))
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    png_filename = f"{session_id}_schedule_page{page_num}.png"
                    
                    cloud_png_path = upload_to_cloudinary_bytes(pix.tobytes("png"), png_filename, resource_type="image", project_name=project_name)
                    if cloud_png_path:
                        active_paths.append(cloud_png_path)
            except Exception as e:
                logger.error(f"[{session_id}] Failed to convert schedule PDF pages to images: {e}")
                from fastapi import HTTPException
                raise HTTPException(status_code=500, detail=f"Failed to process PDF pages: {str(e)}")
        else:
            cloud_file_path = upload_to_cloudinary_bytes(content, filename, resource_type="image", project_name=project_name)
            if cloud_file_path:
                active_paths.append(cloud_file_path)

        from app.services.agents.layer1_schedule.schedule_parser import schedule_parser_agent
        
        try:
            results = await schedule_parser_agent.process_schedule(active_paths)
            return {"status": "success", "schedule_registry": results}
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to parse schedule: {str(e)}")

    async def crop_schedule(self, conn, session_id: str, user_id: int, file, x0: float, y0: float, x1: float, y1: float, page_num: int) -> dict:
        row = estimation_repo.get_draft_session(conn, session_id, user_id)
        if not row:
            from app.core.exceptions import NotFoundException
            raise NotFoundException("Draft session not found")
            
        ext = os.path.splitext(file.filename)[1].lower()
        if ext != ".pdf":
            from app.core.exceptions import ValidationException
            raise ValidationException("Crop extraction is only supported for PDF files.")
            
        import tempfile
        import uuid
        temp_dir = tempfile.gettempdir()
        temp_file_name = f"{session_id}_{uuid.uuid4().hex[:8]}_crop.pdf"
        temp_file_path = os.path.join(temp_dir, temp_file_name)
        
        try:
            content = await file.read()
            with open(temp_file_path, "wb") as f:
                f.write(content)
            try:
                with open(r"c:\Users\Hp\Desktop\Costmate_v3\Backend\uploaded_crop.pdf", "wb") as f:
                    f.write(content)
            except Exception as e:
                logger.error(f"Failed to copy uploaded crop file to workspace: {e}")
        except Exception as e:
            logger.error(f"Failed to save temp file for cropping: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to read/write uploaded file: {str(e)}")
            
        try:
            import pdfplumber
            with pdfplumber.open(temp_file_path) as pdf:
                if page_num < 0 or page_num >= len(pdf.pages):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=400, detail=f"Invalid page number {page_num}. PDF has {len(pdf.pages)} pages.")
                    
                page = pdf.pages[page_num]
                
                left = min(x0, x1)
                top = min(y0, y1)
                right = max(x0, x1)
                bottom = max(y0, y1)
                logger.info(f"[CROP DEBUG] Coordinates: left={left}, top={top}, right={right}, bottom={bottom}, page_num={page_num}")
                logger.info(f"[CROP DEBUG] Page size: width={page.width}, height={page.height}")
                
                cropped_page = page.crop((left, top, right, bottom), relative=True)
                
                tables = cropped_page.find_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 3
                })
                
                if not tables:
                    tables = cropped_page.find_tables(table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text"
                    })
                    
                results = []
                if tables:
                    raw_table = tables[0].extract()
                    logger.info(f"[CROP DEBUG] Extracted table rows count: {len(raw_table) if raw_table else 0}")
                    if raw_table and len(raw_table) >= 5:
                        headers, data_start_idx = self._flatten_headers(raw_table)
                        logger.info(f"[CROP DEBUG] Parsed headers: {headers}, data_start_idx: {data_start_idx}")
                        
                        if headers:
                            headers[0] = "mark"
                            
                        for r_idx, row_data in enumerate(raw_table[data_start_idx:]):
                            if not any(cell for cell in row_data if cell):
                                continue
                                
                            row_dict = {}
                            for col_idx, val in enumerate(row_data):
                                if col_idx < len(headers):
                                    key = headers[col_idx]
                                    if not key:
                                        key = f"COLUMN_{col_idx}"
                                    row_dict[key] = str(val).strip() if val else ""
                                    
                            mark = str(row_dict.get("mark", "")).strip()
                            logger.info(f"[CROP DEBUG] Row {r_idx} mark: '{mark}'")
                            if not mark:
                                continue
                            
                            mark_lower = mark.lower()
                            if mark_lower in {
                                "panel 1", "panel 2", "width", "height", "door number", "mark", 
                                "door details", "door panels", "door frame", "type", "finish 1",
                                "fire rating", "finish", "head", "jamb", "hw set", "comments",
                                "level 1", "level 2", "level 3", "level 4", "level 5", "level 6"
                            } or mark_lower.startswith("level "):
                                logger.info(f"[CROP DEBUG] Skipping row {r_idx} due to filter: '{mark}'")
                                continue
                                
                            row_dict["mark"] = mark.upper()
                            row_dict["needs_review"] = False
                            row_dict["_schedule_type"] = "door"
                            results.append(row_dict)
                            
                if len(results) < 5:
                    logger.info("[CROP FALLBACK] Table extraction returned few rows. Falling back to word coordinate binning...")
                    import re
                    words = cropped_page.extract_words()
                    lines = []
                    for w in words:
                        found = False
                        for line in lines:
                            if abs(line[0]['top'] - w['top']) < 4:
                                line.append(w)
                                found = True
                                break
                        if not found:
                            lines.append([w])
                            
                    lines.sort(key=lambda l: l[0]['top'])
                    
                    fallback_results = []
                    for line in lines:
                        line.sort(key=lambda w: w['x0'])
                        if not line:
                            continue
                        first_w = line[0]['text'].strip()
                        logger.debug(f"[CROP FALLBACK] Candidate row first_w: '{first_w}'")
                        if re.match(r"^([A-Z]{1,2}-?\d+[A-Z]?|\d+[A-Z]?)$", first_w, re.IGNORECASE):
                            row_dict = {
                                "mark": first_w,
                                "FIRE RATING": "",
                                "PANEL 1": "",
                                "PANEL 2": "",
                                "WIDTH 1": "",
                                "WIDTH 2": "",
                                "HEIGHT": "",
                                "PANEL FINISH": "",
                                "FRAME TYPE": "",
                                "FRAME FINISH": "",
                                "HEAD": "",
                                "JAMB": "",
                                "HW SET": "",
                                "COMMENTS": ""
                            }
                            comments_words = []
                            for w in line[1:]:
                                x = w["x0"]
                                txt = w["text"]
                                if 210 <= x < 260:
                                    row_dict["FIRE RATING"] = (row_dict["FIRE RATING"] + " " + txt).strip()
                                elif 260 <= x < 370:
                                    row_dict["PANEL 1"] = (row_dict["PANEL 1"] + " " + txt).strip()
                                elif 370 <= x < 475:
                                    row_dict["PANEL 2"] = (row_dict["PANEL 2"] + " " + txt).strip()
                                elif 475 <= x < 530:
                                    row_dict["WIDTH 1"] = txt
                                elif 530 <= x < 585:
                                    row_dict["WIDTH 2"] = txt
                                elif 585 <= x < 645:
                                    row_dict["HEIGHT"] = txt
                                elif 645 <= x < 830:
                                    row_dict["PANEL FINISH"] = (row_dict["PANEL FINISH"] + " " + txt).strip()
                                elif 830 <= x < 970:
                                    row_dict["FRAME TYPE"] = (row_dict["FRAME TYPE"] + " " + txt).strip()
                                elif 970 <= x < 1100:
                                    row_dict["FRAME FINISH"] = (row_dict["FRAME FINISH"] + " " + txt).strip()
                                elif 1100 <= x < 1150:
                                    row_dict["HEAD"] = txt
                                elif 1150 <= x < 1200:
                                    row_dict["JAMB"] = txt
                                elif 1200 <= x < 1270:
                                    row_dict["HW SET"] = txt
                                elif 1270 <= x:
                                    comments_words.append(txt)
                            if comments_words:
                                row_dict["COMMENTS"] = " ".join(comments_words)
                                
                            row_dict["needs_review"] = False
                            row_dict["_schedule_type"] = "door"
                            fallback_results.append(row_dict)
                    
                    if fallback_results:
                        logger.info(f"[CROP FALLBACK] Successfully extracted {len(fallback_results)} rows using word coordinate binning.")
                        results = fallback_results
                        
                return {"status": "success", "schedule_registry": results}
                
        except Exception as err:
            logger.error(f"Error extracting cropped schedule: {err}")
            import traceback
            traceback.print_exc()
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to crop and parse table: {str(err)}")
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
                    
    def _flatten_headers(self, raw_table: list) -> tuple:
        if not raw_table or not raw_table[0]:
            return [], 0
            
        num_cols = len(raw_table[0])
        
        header_rows = 1
        if len(raw_table) > 1:
            row0 = raw_table[0]
            row1 = raw_table[1]
            if len(row0) > 0 and len(row1) > 0:
                if (not row1[0] or str(row1[0]).strip() == "") and any(cell for cell in row1 if cell):
                    header_rows = 2
                
        headers = []
        
        if header_rows == 2:
            filled_row0 = []
            last_val = ""
            for cell in raw_table[0]:
                c_str = str(cell).strip() if cell else ""
                if c_str:
                    last_val = c_str
                filled_row0.append(last_val)
                
            while len(filled_row0) < num_cols:
                filled_row0.append("")
                
            row1 = raw_table[1]
            for col_idx in range(num_cols):
                p_val = filled_row0[col_idx]
                sub_val = ""
                if col_idx < len(row1):
                    sub_val = str(row1[col_idx]).strip() if row1[col_idx] else ""
                    
                if p_val and sub_val:
                    key = f"{p_val} {sub_val}"
                elif p_val:
                    key = p_val
                else:
                    key = sub_val
                headers.append(key.strip())
            data_start_idx = 2
        else:
            for cell in raw_table[0]:
                headers.append(str(cell).strip() if cell else "")
            data_start_idx = 1
            
        return headers, data_start_idx

    async def quick_scan_draft(self, conn, session_id: str, user_id: int) -> dict:
        # Bypassed VLM room scanning during draft setup to save cost and latency
        return {"rooms": []}

        from app.core.openrouter_client import openrouter_client, parse_json_response
        
        images_to_scan = page_paths if page_paths else [file_path]
        
        prompt = """
        Analyze this floor plan and extract the list of rooms and their dimensions.
        Return ONLY valid JSON in this exact structure:
        {
            "rooms": [
                {
                    "name": "Bedroom",
                    "dimensions": "10x12 ft",
                    "bounding_box": [ymin, xmin, ymax, xmax] 
                }
            ]
        }
        Include an approximate bounding box ratio (0.0 to 1.0) for where you found the room name.
        Do not include any markdown formatting, just raw JSON.
        """
        
        try:
            res_text = await openrouter_client.generate_chat(prompt=prompt, image_paths=[images_to_scan[0]], json_mode=True)
            parsed = parse_json_response(res_text)
            
            # --- OPTION B: PIXEL PERFECT OCR FOR PDFs ---
            try:
                import fitz
                from rapidfuzz import process, fuzz
                import os
                if file_path and file_path.lower().endswith(".pdf"):
                    try:
                        import urllib.request
                        req = urllib.request.Request(file_path, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req) as response:
                            pdf_bytes = response.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    except Exception as e:
                        logger.error(f"Failed to fetch PDF for OCR: {e}")
                        doc = []
                    if len(doc) > 0:
                        page = doc.load_page(0)
                        page_width = page.rect.width
                        page_height = page.rect.height
                        
                        # Extract words: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                        words = page.get_text("words")
                        
                        # Combine words into chunks for better matching
                        text_chunks = []
                        for w in words:
                            text_chunks.append({
                                "text": w[4].strip(),
                                "bbox": [w[1]/page_height, w[0]/page_width, w[3]/page_height, w[2]/page_width] # ymin, xmin, ymax, xmax
                            })
                            
                        # Fuzzy match each room name
                        if "rooms" in parsed and text_chunks:
                            chunk_texts = [c["text"] for c in text_chunks]
                            for room in parsed["rooms"]:
                                name = room.get("name", "")
                                if name:
                                    # Split room name and find best matching words
                                    parts = name.split()
                                    matched_bboxes = []
                                    for part in parts:
                                        if len(part) < 3: continue
                                        match = process.extractOne(part, chunk_texts, scorer=fuzz.ratio)
                                        if match and match[1] > 80: # 80% similarity
                                            idx = match[2]
                                            matched_bboxes.append(text_chunks[idx]["bbox"])
                                            
                                    if matched_bboxes:
                                        # Merge bounding boxes
                                        ymin = min(b[0] for b in matched_bboxes)
                                        xmin = min(b[1] for b in matched_bboxes)
                                        ymax = max(b[2] for b in matched_bboxes)
                                        xmax = max(b[3] for b in matched_bboxes)
                                        
                                        # Add some padding
                                        padding_y = 0.01
                                        padding_x = 0.01
                                        room["bounding_box"] = [
                                            max(0, ymin - padding_y),
                                            max(0, xmin - padding_x),
                                            min(1, ymax + padding_y),
                                            min(1, xmax + padding_x)
                                        ]
            except Exception as ocr_err:
                logger.error(f"Failed to refine OCR bounding boxes: {ocr_err}")
                
            return {"status": "success", "data": parsed}
        except Exception as e:
            logger.error(f"Quick scan failed: {e}")
            raise HTTPException(status_code=500, detail="Quick scan failed")

    async def upload_draft_specification(self, conn, session_id: str, user_id: int, file) -> dict:
        row = estimation_repo.get_draft_session(conn, session_id, user_id)
        if not row:
            raise NotFoundException("Draft session not found")
        project_name = row[0]
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".docx", ".dotx", ".doc", ".dot", ".txt", ".pdf"]:
            raise ValidationException("Invalid specifications file format. Only PDF, .docx, .dotx, .doc, .dot, and .txt are supported.")
            
        filename = f"{session_id}_spec{ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save specifications file: {str(e)}")
            
        spec_text = ""
        if ext in [".docx", ".dotx"]:
            from app.services.agents.layer1_schedule.docx_parser import extract_docx_text
            spec_text = extract_docx_text(file_path)
        elif ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                text_list = [page.get_text() for page in doc]
                spec_text = "\n".join(text_list)
            except Exception as e:
                logger.error(f"Failed to parse PDF spec: {e}")
        else:
            try:
                spec_text = content.decode("utf-8", errors="ignore")
            except Exception as e:
                logger.error(f"Failed to decode TXT spec: {e}")
                
        try:
            os.remove(file_path)
        except:
            pass
            
        return {"status": "success", "specifications_text": spec_text, "filename": file.filename}

    def complete_draft_session(self, conn, session_id: str, user_id: int, intake_data: dict = None) -> dict:
        row = estimation_repo.get_draft_session(conn, session_id, user_id)
        if not row:
            raise NotFoundException("Draft session not found")
        project_name, file_path, original_filename, page_paths, status = row
        if status != "file_uploaded" or not file_path:
            raise ValidationException("Cannot complete session without a file upload")

        estimation_repo.mark_draft_complete(conn, session_id, user_id)
        conn.commit()

        # Gather all uploaded page paths from intake_data floors to process them all
        all_page_paths = []
        if intake_data and "floors" in intake_data:
            for floor in intake_data.get("floors", []):
                if floor.get("pageUrls"):
                    all_page_paths.extend(floor["pageUrls"])
                    
        # Fallback to the session's single page_paths if intake_data is missing
        if not all_page_paths:
            all_page_paths = page_paths or []

        # Get specifications_text if passed in the intake_data
        specifications_text = ""
        if intake_data and isinstance(intake_data, dict):
            specifications_text = intake_data.get("specifications_text", "")
            if not specifications_text:
                specifications_text = intake_data.get("globalSettings", {}).get("specificationsText", "")
                if not specifications_text:
                    specifications_text = intake_data.get("globalSettings", {}).get("specifications_text", "")

        session_manager.start_session(
            session_id=session_id,
            uploaded_file_path=file_path,
            uploaded_page_paths=all_page_paths,
            original_filename=original_filename,
            user_id=user_id,
            project_name=project_name,
            intake_data=intake_data,
            specifications_text=specifications_text
        )
        return {
            "session_id": session_id,
            "status": "processing",
            "project_name": project_name
        }

    async def submit_qa(self, session_id: str, verified_qa: dict, user_id: int) -> dict:
        restored = await session_manager.restore_session_if_needed(session_id, user_id=user_id)
        if not restored:
            raise NotFoundException("Session not found or expired.")
        queue = session_manager.get_queue(session_id)
        if not queue:
            raise NotFoundException("Session not found or expired.")
            
        session_manager.resume_session(session_id, verified_qa)
        return {"status": "resumed"}

estimation_service = EstimationService()
