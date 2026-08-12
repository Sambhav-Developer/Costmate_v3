import json
import asyncio
from typing import List, Dict
from app.core.openrouter_client import OpenRouterClient
from app.core.logging import logger
from app.services.agents.schemas import ScheduleData

class ScheduleParserAgent:
    def __init__(self):
        self.llm = OpenRouterClient()
        
    def _parse_json_safe(self, text: str) -> any:
        try:
            # Try finding the first '[' or '{' to avoid markdown code blocks
            start_idx = -1
            for i, c in enumerate(text):
                if c in ['{', '[']:
                    start_idx = i
                    break
            
            end_idx = -1
            for i in range(len(text)-1, -1, -1):
                if text[i] in ['}', ']']:
                    end_idx = i
                    break
                    
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                clean_text = text[start_idx:end_idx+1]
                return json.loads(clean_text)
            return json.loads(text)
        except Exception as e:
            logger.error(f"JSON Parse failed: {e}\nRaw Text: {text}")
            return None

    async def process_schedule(self, image_paths: List[str]) -> List[Dict]:
        """
        Runs dual-read consensus on schedule tables.
        """
        # Read 1: Extract full table
        prompt_1 = """
        You are a highly precise architectural data extraction engine.
        Extract the COMPLETE schedule table from this image (Door Schedule or Window Schedule).
        Output a JSON array where each element is one data row (NOT header rows).

        CRITICAL RULES FOR JSON KEYS:
        1. The FIRST column (Mark / Mark No / Door No / Window No) MUST always use the key "mark".
        2. Transcribe "mark" EXACTLY as printed — preserve every hyphen, space, letter, and digit character-for-character. Do NOT normalize, reformat, add, or remove any characters.
        3. For ALL other columns, use the EXACT text from the column header as the JSON key.
        4. If a column header is multi-line (e.g. "HARDWARE" on one line, "GROUP NO" below it), join with a single space: "HARDWARE GROUP NO".
        5. DUPLICATE & OVERLAPPING COLUMN NAMES: Schedules often repeat the same header word under different parent groups (e.g. "Material" under both DOOR and FRAME, or "Type"). You MUST prefix these columns to prevent duplicate/overwritten keys in the JSON output:
           - Columns under "DOOR" parent (e.g. Type, Material) -> ALWAYS prefix with "DOOR " -> e.g. "DOOR TYPE", "DOOR MATERIAL"
           - Columns under "FRAME" parent (e.g. Type, Material) -> ALWAYS prefix with "FRAME " -> e.g. "FRAME TYPE", "FRAME MATERIAL"
           - Columns under "DETAIL" parent (e.g. Head, Jamb) -> ALWAYS prefix with "DETAIL " -> e.g. "DETAIL HEAD", "DETAIL JAMB"
        6. STANDALONE COLUMNS (not under any parent group, or only appear once) -> use EXACT header text as-is with NO prefix.
           - A "GLAZING" column standing alone (not visually under DOOR or FIRE RATING) -> "GLAZING"
           - "WIDTH", "HEIGHT", "THICKNESS", "COMMENTS" -> use the exact header name as-is as they appear in the image. If the image has a single column named "WIDTH", use "WIDTH" (do NOT use "Width A" or "Width B" unless those are explicitly printed as separate columns in the image).
        7. Read the table structure top-to-bottom carefully:
           - A "GLAZING" column positioned between DETAIL and FIRE RATING is standalone -> key is "GLAZING", NOT "FIRE RATING GLAZING"
           - Only add "FIRE RATING " prefix to columns visually grouped under the "FIRE RATING" header row
        8. Empty cells -> use empty string "". Never omit a key from a row.
        9. Preserve the left-to-right column order exactly as seen in the image.

        EXAMPLE — a typical Door & Frame schedule row:
        {
          "mark": "D-1",
          "WIDTH": "3'-0\\"",
          "HEIGHT": "7'-0\\"",
          "THICKNESS": "1 3/4\\"",
          "DOOR MATERIAL": "WD",
          "DOOR TYPE": "F",
          "DOOR FINISH": "IRWC-1",
          "DOOR GLAZING": "",
          "FRAME MATERIAL": "HM",
          "FRAME TYPE": "S",
          "FRAME FINISH": "",
          "DETAIL HEAD": "E1/A700",
          "DETAIL JAMB": "E2/A700",
          "DETAIL SILL": "",
          "GLAZING": "",
          "FIRE RATING LABEL": "45 MINS",
          "HARDWARE GROUP NO": "3",
          "COMMENTS": ""
        }

        Do NOT output anything except the JSON array. No markdown fences, no explanations.
        """

        # Read 2: Extract mark auditor consensus list
        prompt_2 = """
        You are a highly precise architectural auditor. Look at the schedule table in this image.
        List EVERY value in the first column (MARK / Door No / Window Mark), in the order they appear top to bottom. Do not skip rows, do not merge rows, do not invent rows.

        Output MUST be a JSON array of strings, e.g.: ["D-1", "D-2", "W-1", "W-2A"]

        Do not output anything else — no markdown fences, no explanations.
        """
        
        # Run Pass 1 and Pass 2 concurrently to optimize response time
        logger.info("ScheduleParser: Running Pass 1 & Pass 2 concurrently...")
        res1_text, res2_text = await asyncio.gather(
            self.llm.generate_chat(prompt=prompt_1, image_paths=image_paths, json_mode=True, temperature=0.1),
            self.llm.generate_chat(prompt=prompt_2, image_paths=image_paths, json_mode=True, temperature=0.4)
        )
        
        res1_data = self._parse_json_safe(res1_text)
        if isinstance(res1_data, dict) and "data" in res1_data:
            res1_data = res1_data["data"]
        
        if not isinstance(res1_data, list):
            res1_data = []
        
        res2_marks = self._parse_json_safe(res2_text)
        if isinstance(res2_marks, dict):
            res2_marks = res2_marks.get("marks") or res2_marks.get("data") or []
            
        if not isinstance(res2_marks, list):
            res2_marks = []
            
        # Extract normalized mark set in Python for robust consensus matching
        import re
        mark_set_2_norm = set()
        for m in res2_marks:
            if isinstance(m, dict):
                norm = re.sub(r'[^A-Z0-9]', '', str(m.get("mark", "")).upper())
            else:
                norm = re.sub(r'[^A-Z0-9]', '', str(m).upper())
            if norm:
                mark_set_2_norm.add(norm)
        
        # Exact mark-like key candidates
        MARK_KEY_CANDIDATES = {
            "mark", "marks", "mark no", "mark no.", "door no", "door no.",
            "window no", "window no.", "window mark", "door mark", "id", "mark / type", "mark/type"
        }
        
        final_schedule = []
        for row in res1_data:
            if not isinstance(row, dict):
                continue
            
            # Clean internal helper keys if present
            row.pop("mark_normalized", None)
            row.pop("mark_norm", None)
            
            mark = str(row.get("mark", "")).strip().upper()
            
            if not mark:
                # Fallback: check for common mark-column key variants
                for k in list(row.keys()):
                    if str(k).lower().strip() in MARK_KEY_CANDIDATES:
                        mark = str(row[k]).strip().upper()
                        if mark:
                            row["mark"] = mark
                            break
                        
            if not mark:
                continue
            
            # Normalize: ensure the canonical "mark" key is always present
            row["mark"] = mark
            
            # Compute normalized mark for robust consensus matching in Python
            mark_norm = re.sub(r'[^A-Z0-9]', '', mark)
                
            needs_review = mark_norm not in mark_set_2_norm
            if needs_review:
                logger.warning(f"Consensus failure for MARK: {mark} (norm: {mark_norm})")
                
            row_data = {**row, "needs_review": needs_review}
            
            # Use Pydantic for validation and filling missing defaults
            try:
                validated = ScheduleData(**row_data)
                out_dict = validated.model_dump(by_alias=True)
                out_dict.pop("mark_normalized", None)
                final_schedule.append(out_dict)
            except Exception as e:
                logger.error(f"Row validation failed for {mark}: {e}")
                # Append anyway with review flag for fault tolerance
                row_data["needs_review"] = True
                row_data.pop("mark_normalized", None)
                final_schedule.append(row_data)
                
        return final_schedule

schedule_parser_agent = ScheduleParserAgent()
