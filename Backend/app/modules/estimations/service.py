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
                
                results = []
                words = cropped_page.extract_words()
                # Filter out empty or whitespace-only texts
                words = [w for w in words if w["text"].strip()]
                
                if words:
                    # 1. Detect column bounds list (Strategy A: Use vertical grid lines if they exist in vector PDF)
                    vertical_lines = [e for e in cropped_page.vertical_edges if (e["y1"] - e["y0"]) >= 12.0]
                    crop_height = bottom - top
                    
                    # Group vertical edges into X-clusters (within 2.5 points)
                    clusters = [] # list of (mean_x, [edges])
                    for edge in vertical_lines:
                        x = edge["x0"]
                        found = False
                        for idx, (mean_x, edges) in enumerate(clusters):
                            if abs(x - mean_x) <= 2.5:
                                edges.append(edge)
                                new_mean = sum(e["x0"] for e in edges) / len(edges)
                                clusters[idx] = (new_mean, edges)
                                found = True
                                break
                        if not found:
                            clusters.append((x, [edge]))
                            
                    # Filter clusters by total length of edges in the cluster (at least 30% of crop height)
                    min_total_len = crop_height * 0.3
                    clustered_xs = []
                    for mean_x, edges in clusters:
                        total_len = sum(e["y1"] - e["y0"] for e in edges)
                        if total_len >= min_total_len:
                            clustered_xs.append(mean_x)
                            
                    clustered_xs = sorted(clustered_xs)
                    
                    merged_spans = []
                    if len(clustered_xs) >= 3:
                        logger.info(f"[CROP DYNAMIC] Using {len(clustered_xs)} detected vertical grid lines for column bounds.")
                        min_word_x = min(w["x0"] for w in words)
                        max_word_x = max(w["x1"] for w in words)
                        
                        if min_word_x < clustered_xs[0] - 8:
                            clustered_xs.insert(0, round(min_word_x - 3, 1))
                        if max_word_x > clustered_xs[-1] + 8:
                            clustered_xs.append(round(max_word_x + 3, 1))
                            
                        for i in range(len(clustered_xs) - 1):
                            merged_spans.append((clustered_xs[i], clustered_xs[i+1]))
                    else:
                        # Strategy B: Fallback to text projection (for borderless or scanned tables)
                        logger.info("[CROP DYNAMIC] Few vertical grid lines detected. Falling back to X-axis text projection...")
                        
                        # Helper to check if a word looks like a mark
                        import re
                        def is_mark_text(text):
                            text_lower = text.lower()
                            header_keywords = {
                                "mark", "number", "door", "window", "frame", "schedule", "type", "finish",
                                "comments", "level", "sheet", "code", "id", "tag", "fire", "rating", "width",
                                "height", "hw", "set", "head", "jamb", "panel", "pane", "dimensions"
                            }
                            if text_lower in header_keywords:
                                return False
                            if re.search(r"\d", text):
                                return True
                            if len(text) <= 4 and text.isupper():
                                return True
                            return False
                            
                        # Classify words horizontally to build raw text rows
                        words.sort(key=lambda w: w['top'])
                        rows = []
                        for w in words:
                            found = False
                            for r in rows:
                                if abs(r[0]['top'] - w['top']) < 4:
                                    r.append(w)
                                    found = True
                                    break
                            if not found:
                                rows.append([w])
                                
                        for r in rows:
                            r.sort(key=lambda w: w['x0'])
                        rows.sort(key=lambda r: r[0]['top'])
                        
                        # Find data rows
                        data_rows = []
                        for r in rows:
                            if r and is_mark_text(r[0]['text']):
                                data_rows.append(r)
                                
                        projection_rows = data_rows if data_rows else rows
                        intervals = []
                        for r in projection_rows:
                            for w in r:
                                intervals.append((w['x0'], w['x1']))
                                
                        intervals.sort(key=lambda x: x[0])
                        if intervals:
                            cur_start, cur_end = intervals[0]
                            for start, end in intervals[1:]:
                                if start <= cur_end + 5:
                                    cur_end = max(cur_end, end)
                                else:
                                    merged_spans.append((cur_start, cur_end))
                                    cur_start = start
                                    cur_end = end
                            merged_spans.append((cur_start, cur_end))
                            
                    num_cols = len(merged_spans)
                    logger.info(f"[CROP DYNAMIC] Final columns count: {num_cols}")
                    
                    if num_cols > 0:
                        # 2. Helper to check if a word looks like a mark
                        import re
                        def is_mark_text(text):
                            text_lower = text.lower()
                            header_keywords = {
                                "mark", "number", "door", "window", "frame", "schedule", "type", "finish",
                                "comments", "level", "sheet", "code", "id", "tag", "fire", "rating", "width",
                                "height", "hw", "set", "head", "jamb", "panel", "pane", "dimensions"
                            }
                            if text_lower in header_keywords:
                                return False
                            if re.search(r"\d", text):
                                return True
                            if len(text) <= 4 and text.isupper():
                                return True
                            return False
                            
                        # Find all explicit marks and their Y-centers
                        marks_info = []
                        for w in words:
                            center_x = (w['x0'] + w['x1']) / 2.0
                            # Check if the word is in Column 0
                            if merged_spans[0][0] <= center_x <= merged_spans[0][1]:
                                if is_mark_text(w['text']):
                                    marks_info.append((w['text'], (w['top'] + w['bottom']) / 2.0))
                                    
                        marks_info.sort(key=lambda x: x[1])
                        
                        # Define first data row Y-start boundary
                        first_data_y = float('inf')
                        if marks_info:
                            first_data_y = marks_info[0][1] - 8
                            
                        logger.info(f"[CROP DYNAMIC] Detected {len(marks_info)} marks. First data Y: {first_data_y}")
                        
                        # 3. Group words into Headers and Data Rows
                        header_words = []
                        data_row_words = {}
                        if marks_info:
                            data_row_words = {m_text: [[] for _ in range(num_cols)] for m_text, _ in marks_info}
                            
                        for w in words:
                            center_x = (w['x0'] + w['x1']) / 2.0
                            center_y = (w['top'] + w['bottom']) / 2.0
                            
                            # Find best column index
                            best_col = 0
                            min_dist = float('inf')
                            for col_idx, (start, end) in enumerate(merged_spans):
                                if start <= center_x <= end:
                                    best_col = col_idx
                                    break
                                dist = min(abs(center_x - start), abs(center_x - end))
                                if dist < min_dist:
                                    min_dist = dist
                                    best_col = col_idx
                                    
                            if center_y < first_data_y:
                                header_words.append((w, best_col))
                            elif marks_info:
                                # Find closest mark Y coordinate
                                closest_mark = None
                                min_y_dist = float('inf')
                                for m_text, m_y in marks_info:
                                    dist_y = abs(center_y - m_y)
                                    if dist_y < min_y_dist:
                                        min_y_dist = dist_y
                                        closest_mark = m_text
                                if closest_mark:
                                    data_row_words[closest_mark][best_col].append(w)
                                    
                        # 4. Extract Header names
                        column_headers = [[] for _ in range(num_cols)]
                        for w, col_idx in header_words:
                            column_headers[col_idx].append(w)
                            
                        clean_headers = []
                        seen_keys = {}
                        for col_idx, h_w_list in enumerate(column_headers):
                            # Sort header words top-to-bottom, left-to-right
                            h_w_list.sort(key=lambda w: (w['top'], w['x0']))
                            h_text = " ".join(w['text'] for w in h_w_list).strip()
                            is_empty_header = False
                            if not h_text:
                                h_text = f"COLUMN_{col_idx}"
                                is_empty_header = True
                                
                            base_key = h_text
                            if not is_empty_header:
                                if base_key in seen_keys:
                                    seen_keys[base_key] += 1
                                    h_text = f"{base_key}_{seen_keys[base_key]}"
                                else:
                                    seen_keys[base_key] = 0
                            clean_headers.append(h_text)
                                
                        if clean_headers:
                            clean_headers[0] = "mark"
                            
                        logger.info(f"[CROP DYNAMIC] Unified header keys: {clean_headers}")
                        
                        # 5. Extract data rows
                        raw_results = []
                        # If no marks were found, fall back to simple row grouping
                        if not marks_info:
                            # Group all words into simple rows
                            words.sort(key=lambda w: w['top'])
                            rows = []
                            for w in words:
                                found = False
                                for r in rows:
                                    if abs(r[0]['top'] - w['top']) < 4:
                                        r.append(w)
                                        found = True
                                        break
                                if not found:
                                    rows.append([w])
                            for r in rows:
                                r.sort(key=lambda w: w['x0'])
                            rows.sort(key=lambda r: r[0]['top'])
                            
                            for r in rows:
                                row_dict = {}
                                row_cells = [[] for _ in range(num_cols)]
                                for w in r:
                                    center_x = (w['x0'] + w['x1']) / 2.0
                                    best_col = 0
                                    min_dist = float('inf')
                                    for col_idx, (start, end) in enumerate(merged_spans):
                                        if start <= center_x <= end:
                                            best_col = col_idx
                                            break
                                        dist = min(abs(center_x - start), abs(center_x - end))
                                        if dist < min_dist:
                                            min_dist = dist
                                            best_col = col_idx
                                    row_cells[best_col].append(w['text'])
                                    
                                for col_idx, cell_words in enumerate(row_cells):
                                    val = " ".join(cell_words).strip()
                                    if col_idx < len(clean_headers):
                                        key = clean_headers[col_idx]
                                        row_dict[key] = val
                                        
                                mark = row_dict.get("mark", "").strip()
                                if not mark:
                                    continue
                                row_dict["mark"] = mark.upper()
                                row_dict["needs_review"] = False
                                row_dict["_schedule_type"] = "door"
                                raw_results.append(row_dict)
                        else:
                            for m_text, _ in marks_info:
                                row_dict = {}
                                for col_idx in range(num_cols):
                                    cell_w = data_row_words[m_text][col_idx]
                                    cell_w.sort(key=lambda w: (w['top'], w['x0']))
                                    val = " ".join(w['text'] for w in cell_w).strip()
                                    if col_idx < len(clean_headers):
                                        key = clean_headers[col_idx]
                                        row_dict[key] = val
                                        
                                mark = row_dict.get("mark", "").strip()
                                if not mark:
                                    row_dict["mark"] = m_text.upper()
                                else:
                                    row_dict["mark"] = mark.upper()
                                row_dict["needs_review"] = False
                                row_dict["_schedule_type"] = "door"
                                raw_results.append(row_dict)
                                
                        # Identify empty COLUMN_x columns that have all empty values
                        cols_to_drop = set()
                        for col_idx, key in enumerate(clean_headers):
                            if key.startswith("COLUMN_"):
                                all_empty = all(row.get(key, "") == "" for row in raw_results)
                                if all_empty:
                                    cols_to_drop.add(key)
                                    
                        # Filter out dropped columns from results
                        for row in raw_results:
                            final_row = {k: v for k, v in row.items() if k not in cols_to_drop}
                            results.append(final_row)
                                
                if not results:
                    # Line-based table extraction fallback (e.g. for scanned PDFs or when text projection returns nothing)
                    logger.info("[CROP FALLBACK] Word projection returned no rows. Falling back to line-based table finder...")
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
                    if tables:
                        raw_table = tables[0].extract()
                        if raw_table and len(raw_table) >= 5:
                            headers, data_start_idx = self._flatten_headers(raw_table)
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
                                if not mark:
                                    continue
                                mark_lower = mark.lower()
                                if mark_lower in {
                                    "panel 1", "panel 2", "width", "height", "door number", "mark", 
                                    "door details", "door panels", "door frame", "type", "finish 1",
                                    "fire rating", "finish", "head", "jamb", "hw set", "comments"
                                }:
                                    continue
                                row_dict["mark"] = mark.upper()
                                row_dict["needs_review"] = False
                                row_dict["_schedule_type"] = "door"
                                results.append(row_dict)
                        
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
