import json
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
        2. For ALL other columns, use the EXACT text from the column header as the JSON key.
        3. If a column header is multi-line (e.g. "HARDWARE" on one line, "GROUP NO" below it), join with a single space: "HARDWARE GROUP NO".
        4. DUPLICATE COLUMN NAMES: Schedules often repeat the same header word under different parent groups. You MUST add a prefix ONLY when a column header is directly underneath a named parent-group header AND the same word appears elsewhere in the table too. Rules:
           - Column under "DOOR" parent  → prefix "DOOR "  → e.g. "DOOR MATERIAL", "DOOR TYPE", "DOOR FINISH", "DOOR GLAZING"
           - Column under "FRAME" parent → prefix "FRAME " → e.g. "FRAME MATERIAL", "FRAME TYPE", "FRAME FINISH"
           - Column under "DETAIL" parent → prefix "DETAIL " → e.g. "DETAIL HEAD", "DETAIL JAMB", "DETAIL SILL"
           - Column under "FIRE RATING" parent → prefix "FIRE RATING " → e.g. "FIRE RATING LABEL", "FIRE RATING GLAZING" (only if those sub-columns actually exist under FIRE RATING in the image)
           - Column under "HARDWARE" parent → prefix "HARDWARE " → e.g. "HARDWARE GROUP NO"
        5. STANDALONE COLUMNS (not under any parent group, or only appear once) → use EXACT header text as-is with NO prefix.
           - "GLAZING" that appears as a standalone column (not visually under DOOR or FIRE RATING parent header) → use exactly "GLAZING"
           - "W", "H", "T", "COMMENTS" → use as-is
        6. IMPORTANT — Read the table structure carefully top-to-bottom:
           - A "GLAZING" column positioned between DETAIL (HEAD/JAMB/SILL) and FIRE RATING is a STANDALONE column → key is "GLAZING", NOT "FIRE RATING GLAZING"
           - Only add "FIRE RATING " prefix to columns that are VISUALLY GROUPED under the "FIRE RATING" header row
        7. Empty cells → use empty string "". Never omit a key from a row.
        8. Preserve the left-to-right column order exactly as seen in the image.

        EXAMPLE — a typical Door & Frame schedule row (note: GLAZING is standalone, FIRE RATING only covers LABEL):
        {
          "mark": "D-1",
          "W": "3'-0\\"",
          "H": "7'-0\\"",
          "T": "1 3/4\\"",
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


        # Read 2: Extract just the MARK column for consensus validation
        prompt_2 = """
        You are a highly precise architectural auditor. Look at the schedule table in this image.
        List EVERY single value in the first column (MARK / Door No / Window Mark) of the table, exactly as written.
        Output MUST be a JSON array of strings, e.g. ["D-1", "D-2", "W-1", "W-2A"]
        Do not output anything else.
        """
        
        # Run sequentially because some providers rate-limit concurrent requests
        logger.info("ScheduleParser: Running Pass 1...")
        res1_text = await self.llm.generate_chat(prompt=prompt_1, image_paths=image_paths, json_mode=True, temperature=0.1)
        
        logger.info("ScheduleParser: Running Pass 2...")
        res2_text = await self.llm.generate_chat(prompt=prompt_2, image_paths=image_paths, json_mode=True, temperature=0.4)
        
        res1_data = self._parse_json_safe(res1_text)
        if isinstance(res1_data, dict) and "data" in res1_data:
            res1_data = res1_data["data"]
        
        if not isinstance(res1_data, list):
            res1_data = []
        
        res2_marks = self._parse_json_safe(res2_text)
        if isinstance(res2_marks, dict) and "marks" in res2_marks:
            res2_marks = res2_marks["marks"]
            
        if not isinstance(res2_marks, list):
            res2_marks = []
            
        # Consensus matching
        mark_set_2 = set(str(m).strip().upper() for m in res2_marks)
        
        # Exact mark-like key candidates — do NOT include "no" alone as it matches "HARDWARE GROUP NO"
        MARK_KEY_CANDIDATES = {
            "mark", "mark no", "mark no.", "door no", "door no.",
            "window no", "window no.", "window mark", "door mark", "id"
        }
        
        final_schedule = []
        for row in res1_data:
            if not isinstance(row, dict):
                continue
            
            # The prompt tells the LLM to use "mark" key always; try it first
            mark = str(row.get("mark", "")).strip().upper()
            
            if not mark:
                # Fallback: check for common mark-column key variants (exact match only)
                for k in row.keys():
                    if str(k).lower().strip() in MARK_KEY_CANDIDATES:
                        mark = str(row[k]).strip().upper()
                        if mark:
                            row["mark"] = mark
                            break
                        
            if not mark:
                continue
            
            # Normalize: ensure the canonical "mark" key is always present
            row["mark"] = mark
                
            needs_review = mark not in mark_set_2
            if needs_review:
                logger.warning(f"Consensus failure for MARK: {mark}")
                
            row_data = {**row, "needs_review": needs_review}
            
            # Use Pydantic for validation and filling missing defaults
            try:
                validated = ScheduleData(**row_data)
                final_schedule.append(validated.model_dump(by_alias=True))
            except Exception as e:
                logger.error(f"Row validation failed for {mark}: {e}")
                # Append anyway with review flag for fault tolerance
                row_data["needs_review"] = True
                final_schedule.append(row_data)
                
        return final_schedule

schedule_parser_agent = ScheduleParserAgent()
