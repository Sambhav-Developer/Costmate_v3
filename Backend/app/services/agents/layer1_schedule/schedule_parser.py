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
        Runs dual-pass VLM extraction: full table extraction (Prompt 1) + mark auditor (Prompt 2).
        Both run in parallel. Results are cross-referenced to flag unconfirmed rows as needs_review.
        """

        prompt = """
You are a highly precise architectural data extraction engine.

Extract the COMPLETE schedule table(s) from this image (Door Schedule, Window
Schedule, or Opening/Type Schedule). The image may contain ONE or MULTIPLE
separate tables — process each table independently using its own column
structure, then output ALL data rows from ALL tables as a single flat JSON
array, in top-to-bottom, left-to-right reading order.

Output a JSON array where each element is one data row. Do NOT output header
rows, title rows, or section/category banner rows (see Rule 9).

CRITICAL RULES FOR JSON KEYS:

1. FIRST COLUMN → "mark". The first column of every table is always the row's
   unique identifier, regardless of its printed header text — it may be
   labeled "Mark", "Mark No", "Door No", "Door Number", "Window No",
   "Opening Code", "Opening No", "ID", or similar. Whatever it is called,
   map it to the JSON key "mark".

2. Transcribe "mark" EXACTLY as printed — preserve every hyphen, space,
   letter, digit, and period character-for-character (e.g. "300-01A",
   "RS017B", "A.1", "98C"). Do NOT normalize, reformat, add, or remove
   characters.

3. For all other columns, use the EXACT printed column header text as the
   JSON key — preserve wording, case, abbreviations, and punctuation exactly
   as printed. Do NOT silently expand or "correct" abbreviations.
   Examples: "MAT'L" stays "MAT'L" (not "Material"); "THCKNS" stays "THCKNS"
   (not "Thickness"); "No. OF LEAVES" keeps the period and case as printed.

4. If a column header is visually split across multiple lines, join the
   lines with a single space (e.g. "Hardware Set", "Fire Rating (Mins)").
   Keep any parenthetical units exactly as printed.

5. DUPLICATE HEADERS UNDER NAMED PARENTS: Prefix a column key ONLY when its
   LITERAL PRINTED HEADER TEXT is identical to another column's literal
   printed header text somewhere else in the same table (e.g. two columns
   both literally printed "Material" — one under a DOOR group, one under a
   FRAME group). In that case prefix both with their parent category in ALL
   CAPS: "DOOR MATERIAL", "FRAME MATERIAL".

   Do NOT prefix a column just because it visually sits inside a DOOR/FRAME/
   DETAIL group box. Visual grouping alone is not a collision. If the
   printed text is already distinct — e.g. "Type" under DOOR vs "Frame Type"
   under FRAME, or "Jamb"/"Head" under DETAIL with no other "Jamb"/"Head"
   column anywhere else in the table — leave it exactly as printed, with NO
   prefix, per Rule 7. Getting this wrong in either direction (prefixing
   something unique, or failing to prefix something that collides) is a
   common failure mode — check literal text equality, not box membership,
   before adding any prefix.

6. DUPLICATE HEADERS WITH NO NAMED PARENT: If a header word/phrase repeats
   in the same table but at least one occurrence has NO distinguishing
   parent label above it (e.g. a "GLAZING" column nested under "DOOR", and
   a second standalone "GLAZING" column later in the same row with no group
   header of its own), disambiguate by APPENDING A POSITIONAL NUMBER to
   every occurrence after the first, in left-to-right order:
   first occurrence → "GLAZING", second occurrence → "GLAZING 2", third →
   "GLAZING 3", etc. Do this only when Rule 5's named-parent approach does
   not resolve the collision.

7. UNIQUE HEADERS: If a header is unique in the table (e.g. "Width",
   "Height", "Width A", "Rating", "Comments"), use the exact printed text
   as the key with no prefix. Do not invent or hardcode prefixes for
   columns that don't actually repeat.

8. Every row object in a given table must contain the SAME set of keys, in
   the same left-to-right column order as that table's header — including
   columns that are blank for that particular row.

CELL VALUE RULES:

9. TRUE BLANK cells (visually empty, nothing printed) → use empty string "".
   Do NOT use "" for cells that contain a literal placeholder or code —
   preserve those verbatim instead: "-", "N/A", "EX", "VIF", "EXIST",
   "TS", etc. are real printed values and must be transcribed as-is, not
   collapsed to "".

10. Preserve compound/merged cell values exactly as printed, including
    slash-separated pair dimensions (e.g. "3'-0"/3'-0"") and comma-separated
    multi-reference details (e.g. "5B, 5C, 5D/A611"). Do not split them into
    separate fields unless they are already in separate printed columns.

ROW-LEVEL STRUCTURE RULES:

11. SKIP SECTION/CATEGORY BANNER ROWS: Some schedules include a full-width
    divider row with no per-column data — just a label such as
    "3.0 - THIRD FLOOR", "AREA A", "LEVEL 2", etc. These are section
    headers, not data rows. Do NOT emit a JSON object for them, and do NOT
    let them corrupt the "mark" of adjacent real rows.

12. WRAPPED COMMENT CONTINUATIONS: If a row's Comments (or any long text
    cell) visually wraps onto an additional line, and that continuation
    line has a blank "mark" cell and blank values in all other columns,
    treat it as a continuation of the PREVIOUS row — append the wrapped
    text to that row's Comments value (joined with a space) rather than
    creating a new row object.

13. MULTIPLE TABLES IN ONE IMAGE: If the image contains more than one
    distinct schedule table (different titles, different column sets, or
    a legend/type table alongside an instance schedule), extract each table
    using its own header structure independently. Rows from different
    tables will naturally have different key sets — this is expected. Do
    not attempt to merge different tables' schemas together. Concatenate
    all resulting row objects into one single flat JSON array, in the order
    the tables appear top-to-bottom in the image.

14. Preserve top-to-bottom row order exactly as printed within each table.

15. NO INVENTED KEYS: Every key in every row object must correspond to an
    actual printed column in that table. Never add extra keys that are not
    printed column headers — no "needs_review", no "_schedule_type", no
    confidence scores, no IDs, no metadata of any kind, even if they seem
    helpful. If you are not fully certain of a value, still transcribe your
    best reading of the printed text — do not add a flag field instead.

16. COLUMN-COUNT SELF-CHECK (do this silently before finalizing each table):
    Count the header columns left-to-right, noting exactly which header
    text strings repeat (per Rule 5/6). Every data row must produce exactly
    that many value fields, one per physical column position — never fewer,
    never merged. Pay special attention to any pair of columns that share
    identical header text (like two "Material" columns): these are the most
    common place a column gets silently dropped or overwritten by the
    neighboring column's value. Verify both values are present and came
    from their own column position, not copied from one into the other.

17. WORKED EXAMPLES (anchor your output format on these — same table shape:
    Door No | Width A | Width B | Height | Thickness | Type | Material
    [DOOR] | Frame Type | Material [FRAME] | Jamb | Head | Glazing |
    Hardware Set | Fire Rating (Mins) | Comments):

    Dense row with two distinct Material values (DOOR ≠ FRAME — do not merge):
    {
      "mark": "3C03",
      "Width A": "3'-0\"",
      "Width B": "",
      "Height": "7'-0\"",
      "Thickness": "1 3/4\"",
      "Type": "F",
      "DOOR Material": "WD",
      "Frame Type": "A",
      "FRAME Material": "HM",
      "Jamb": "5C/A611",
      "Head": "5C/A611",
      "Glazing": "-",
      "Hardware Set": "7.0",
      "Fire Rating (Mins)": "",
      "Comments": "CR"
    }

    Sparse row (aluminum storefront door — most cells blank, both Material
    columns still present and populated independently):
    {
      "mark": "300-12A",
      "Width A": "",
      "Width B": "",
      "Height": "",
      "Thickness": "",
      "Type": "",
      "DOOR Material": "AL",
      "Frame Type": "",
      "FRAME Material": "AL",
      "Jamb": "2D/A611",
      "Head": "2B&3B/A611",
      "Glazing": "TS",
      "Hardware Set": "",
      "Fire Rating (Mins)": "",
      "Comments": "AD SYSTEM"
    }

    Row where an entire column group is a repeated placeholder, not blank
    (existing pair door — literal "EXIST" preserved, not converted to ""):
    {
      "mark": "300-01A",
      "Width A": "3'-0\"",
      "Width B": "3'-0\"",
      "Height": "6'-8\"",
      "Thickness": "1 3/4\"",
      "Type": "EXIST",
      "DOOR Material": "EXIST",
      "Frame Type": "EXIST",
      "FRAME Material": "EXIST",
      "Jamb": "EXIST",
      "Head": "EXIST",
      "Glazing": "-",
      "Hardware Set": "5.2",
      "Fire Rating (Mins)": "",
      "Comments": "EXIST, 2 AUTOMATIC, CR, NOTE B, NOTE C"
    }

    A row that must be SKIPPED entirely (section banner, not data) — do not
    emit any object for a row that just says, e.g., "3.0 - THIRD FLOOR"
    spanning the row with no per-column values.

18. USE THE KNOWN SCHEDULE LAYOUTS (below) to help you recognize which
    project's column structure you're looking at, and to resolve ambiguity
    when the header row is dense, abbreviated, or hard to read. This is a
    CLASSIFICATION AID ONLY:
    - It never overrides Rule 3 (use the exact printed text, character for
      character, as it appears in THIS image).
    - It never overrides Rule 5/6 (prefix only on literal text collision,
      or positional suffix when no named parent distinguishes a repeat).
    - If the image's headers don't match any known layout, or only
      partially match, that's fine — extract exactly what's printed using
      Rules 1–17. These templates describe patterns seen before, not a
      fixed menu of allowed columns.

    IMPORTANT — DO NOT STRIP ALREADY-DISAMBIGUATED PRINTED TEXT: Some
    projects print fully spelled-out, already-unique headers directly on
    the schedule itself (e.g. "Door Finish", "Detail Head", "Hardware
    Group No"). These are NOT synthetic prefixes added by our rules — they
    are the literal printed header. Transcribe them in full exactly as
    printed. Only remove/add a prefix when RULE 5 or RULE 6 requires you to
    synthesize one because of an actual text collision within that image.

    KNOWN SCHEDULE LAYOUTS SEEN ACROSS PROJECTS:

    Layout 1 — mark: "Door No"
      Door No, Width A, Width B, Height, Thickness, Door Type,
      Door Material, Frame Type, Frame Material, Jamb, Head, Glazing,
      Hardware Set, Fire Rating, Comments
      Notes: Door Type/Frame Type and Door Material/Frame Material are
      ALREADY distinct printed text in this layout — no synthesized prefix
      needed. Jamb/Head are unique, printed bare, no "Detail" prefix here.

    Layout 2 — mark: "Door Number"
      Door Number, Door Type, Width, Height, Door Material, Frame Type,
      Frame Material, Hardware Set, Comments
      Notes: single Width/Height (no A/B split). Everything already
      disambiguated in the printed text — transcribe as-is.

    Layout 3 — mark: "MARK"
      MARK, W, H, T, Door Material, Door Type, Door Finish, Door Glazing,
      Frame Material, Frame Type, Frame Finish, Detail Head, Detail Jamb,
      Detail Sill, Glazing, Fire Rating LABEL, Hardware Group No, Comments
      Notes: W/H/T are genuinely printed as single letters in this
      layout — transcribe as "W"/"H"/"T" verbatim, do not expand to
      "Width"/"Height"/"Thickness". "Door Glazing" and the later bare
      "Glazing" are two textually DISTINCT columns (door-side vs
      frame-side glazing) — keep both exactly as printed, they are not a
      collision. "Detail Head"/"Detail Jamb"/"Detail Sill" are printed in
      full on this schedule — keep the "Detail" word, don't shorten it.

    Layout 4 — mark: "Opening Code"
      Opening Code, General Description, Fire Rating, Door Panel Type,
      Door Material, Door Finish, No. of Leaves, Width, Height, Thickness,
      Frame Type, Frame Material, Finish, Jamb, Head, Comments
      Notes: the LAST "Finish" (bare, no prefix) is the FRAME's finish
      column — "Door Finish" already appeared earlier for the door side, so
      this later bare "Finish" is understood by position, not by adding a
      synthetic "Frame" prefix (the source printed it bare — transcribe key
      as "Finish", not "Frame Finish", unless Rule 5 applies to it because
      "Finish" also repeats elsewhere unprefixed).
      ABBREVIATION QUIRK: on the actual printed schedule for this layout,
      "Material" appears as "MAT'L" (e.g. "Door MAT'L", "Frame MAT'L") and
      "Thickness" appears as "THCKNS". Transcribe those exact abbreviated
      strings as the header text — do not silently expand them to
      "Material"/"Thickness".

    Layout 5 — mark: "Door No."
      Door No., Room, Door Type, Frame Type, Width, Height, Elevation,
      Hardware Set, Fire Rating, Comments
      Notes: mark header includes a trailing period — preserve it exactly
      ("Door No.", not "Door No"). "Room" is a location field, "Elevation"
      is a distinct reference column — both unique, no prefixing needed.

KNOWN LAYOUTS END. Return to normal extraction using Rules 1–17, applying
these layouts only as recognition/classification guidance — always defer
to what is literally printed in the actual image over any template above.

OUTPUT FORMAT:

Do NOT output anything except the JSON array. No markdown fences, no
commentary, no explanations, no trailing text before or after the array.

HARDWARE COLUMN SPECIAL ATTENTION:
The "Hardware Set" (or "Hardware Group No") column appears near the right end of the table,
immediately BEFORE the "Fire Rating" column. Its value is always a short number or code
(e.g. "1.0", "4.2", "7.0", "9.1", "AD SYSTEM"). The "Fire Rating" column immediately to
its right is typically blank or contains a duration like "45 MINS" or "1 HR".
NEVER swap these two values. If you see a number like "7.0" in the Hardware column position,
it belongs to "Hardware Set", NOT to "Fire Rating".
"""

        prompt_2 = """
You are a highly precise architectural auditor. Look at the schedule table in this image.
List EVERY value in the first column (MARK / Door No / Window Mark), in the order they appear
top to bottom. Do not skip rows, do not merge rows, do not invent rows.
Skip any full-width section/category divider rows (e.g. "3.0 - THIRD FLOOR", "AREA A", "LEVEL 2").

Output MUST be a JSON array of strings, e.g.: ["D-1", "D-2", "W-1", "W-2A"]
Do not output anything else — no markdown fences, no explanations.
"""

        logger.info("ScheduleParser: Running dual-pass VLM extraction (Prompt 1 + Mark Auditor)...")
        
        import re
        final_schedule = []
        for img_path in image_paths:
            try:
                # Run both passes in parallel for same latency as single-pass
                res1_text, res2_text = await asyncio.gather(
                    self.llm.generate_chat(
                        prompt=prompt,
                        image_paths=[img_path],
                        json_mode=True,
                        temperature=0.1,
                        model_name="qwen/qwen2.5-vl-72b-instruct"
                    ),
                    self.llm.generate_chat(
                        prompt=prompt_2,
                        image_paths=[img_path],
                        json_mode=True,
                        temperature=0.4,
                        model_name="qwen/qwen2.5-vl-72b-instruct"
                    )
                )
                logger.info("ScheduleParser: Both VLM passes completed. Cross-referencing marks...")

                res_data = self._parse_json_safe(res1_text)
                if isinstance(res_data, dict) and "data" in res_data:
                    res_data = res_data["data"]
                if not isinstance(res_data, list):
                    logger.warning(f"Unexpected response structure from LLM for {img_path}: {res1_text}")
                    continue

                # Build normalized mark audit set from Prompt 2
                res2_marks = self._parse_json_safe(res2_text)
                if not isinstance(res2_marks, list):
                    res2_marks = []
                mark_set_audit = set()
                for m in res2_marks:
                    norm = re.sub(r'[^A-Z0-9]', '', str(m).upper())
                    if norm:
                        mark_set_audit.add(norm)
                logger.info(f"ScheduleParser: Auditor confirmed {len(mark_set_audit)} unique marks.")
                    
                # Exact mark-like key candidates
                MARK_KEY_CANDIDATES = {
                    "mark", "marks", "mark no", "mark no.", "door no", "door no.",
                    "window no", "window no.", "window mark", "door mark", "id", "mark / type", "mark/type"
                }
                
                for row in res_data:
                    if not isinstance(row, dict):
                        continue
                    
                    row.pop("mark_normalized", None)
                    row.pop("mark_norm", None)
                    
                    mark = str(row.get("mark", "")).strip().upper()
                    if not mark:
                        for k in list(row.keys()):
                            if str(k).lower().strip() in MARK_KEY_CANDIDATES:
                                mark = str(row[k]).strip().upper()
                                if mark:
                                    row["mark"] = mark
                                    break
                    if not mark:
                        continue
                        
                    row["mark"] = mark

                    # Cross-reference: flag if mark not confirmed by auditor pass
                    mark_norm = re.sub(r'[^A-Z0-9]', '', mark)
                    needs_review = bool(mark_set_audit) and mark_norm not in mark_set_audit
                    if needs_review:
                        logger.warning(f"ScheduleParser: ⚠️ Mark '{mark}' not confirmed by auditor — flagged for review.")

                    row_data = {**row, "needs_review": needs_review}
                    
                    try:
                        validated = ScheduleData(**row_data)
                        out_dict = validated.model_dump(by_alias=True)
                        out_dict.pop("mark_normalized", None)
                        final_schedule.append(out_dict)
                    except Exception as e:
                        logger.error(f"Row validation failed for {mark}: {e}")
                        row_data.pop("mark_normalized", None)
                        final_schedule.append(row_data)
            except Exception as ex:
                logger.error(f"Failed to parse schedule page {img_path}: {ex}")
                
        return final_schedule

schedule_parser_agent = ScheduleParserAgent()
