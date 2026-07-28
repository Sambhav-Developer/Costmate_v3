from app.services.graph.state import CostmateState
from app.core.logging import logger
from langgraph.types import interrupt
import json
import os
import re
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.core.floor_utils import normalize_floor_name

async def prefill_qa_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: Q&A PRE-FILL NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 🕒 Consolidating findings from vision LLMs...")
    
    # 3. Fetch elements detected (doors and windows)
    elements_data = state.get("elements", {})
    
    doors = elements_data.get("doors", [])
    windows = elements_data.get("windows", [])

    # Extract Project Metadata (Name of Work & Sub Work)
    ocr_text = state.get("raw_ocr_text", "")
    original_filename = state.get("original_filename", "")
    
    project_name = ""
    sub_work_name = ""
    
    if ocr_text:
        try:
            logger.info(f"[{session_id}] Prompting OpenRouter to extract project and sub-work details from OCR text...")
            prompt = f"""You are an expert civil engineering assistant.
We have uploaded a design drawing file.
Original Filename: {original_filename}
Extracted OCR Text from the drawing:
{ocr_text}

Task:
Identify the official "Name of Work" (Project Name) and "Sub Work Name" (specific building name/section/purpose of the drawing) from the drawing's OCR text or legend details.
1. "project_name": The formal, complete, official Name of Work. Ensure it starts with terms like "Proposed Construction of...", "Estimate of...", or whatever is written in the drawing title blocks. If not explicitly found in OCR, derive a clean title from the filename.
2. "sub_work_name": A short 2-5 word label of the specific building block or section (e.g. "Residential Building", "2 Wheeler Facility", "Commercial Building", "Main Block").

Return the result strictly as a JSON object:
{{
  "project_name": "...",
  "sub_work_name": "..."
}}"""
            response_text = await openrouter_client.generate_chat(
                prompt=prompt,
                json_mode=True
            )
            parsed = parse_json_response(response_text)
            project_name = parsed.get("project_name", "").strip()
            sub_work_name = parsed.get("sub_work_name", "").strip()
            logger.info(f"[{session_id}] OpenRouter successfully extracted project_name: '{project_name}', sub_work_name: '{sub_work_name}'")
        except Exception as e:
            logger.error(f"[{session_id}] Failed to extract project details via OpenRouter: {e}")

    # Fallbacks if LLM fails or returns empty values
    if not project_name:
        if original_filename:
            base_filename = os.path.splitext(original_filename)[0]
            uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
            if not uuid_pattern.match(base_filename):
                project_name = base_filename.replace("_", " ").replace("-", " ").title()
            
    if not project_name:
        project_name = "Estimate of Building"
        
    if not sub_work_name:
        sub_work_name = project_name

    # Build prefilled structure
    prefilled = {
        "project_name": project_name,
        "sub_work_name": sub_work_name,
        "raw_ocr_text": ocr_text,
        "doors": doors,
        "windows": windows
    }

    logger.info(f"----------------------------------------------------------------------\n"
                f"✅ [{session_id}] COMPLETED: Q&A PRE-FILL NODE\n"
                f"  ├─ 🕒 Status: Success\n"
                f"  ├─ 📊 Generated prefilled floors: {len(prefilled.get('floors', []))} floors\n"
                f"  ├─ 🏛️ Columns configured: {len(prefilled.get('columns', []))}\n"
                f"  └─ 🧱 Project Name: '{prefilled.get('project_name')}'\n"
                f"======================================================================")
    return {
        "qa_prefilled": prefilled,
        "current_step": "qa_prefilled",
        "progress_pct": 40
    }

async def interrupt_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"\n======================================================================\n"
                f"⏸️ [{session_id}] RESUMING: INTERRUPT NODE\n"
                f"----------------------------------------------------------------------")
    
    qa_verified = state.get("qa_verified")
    if not qa_verified:
        logger.warning(f"  ⚠️ [{session_id}] interrupt_node ran but no qa_verified data was found in state.")
    else:
        logger.info(f"  🎉 [{session_id}] User-verified Q&A responses loaded successfully!\n"
                    f"  ├─ 🏢 Verified Floors: {qa_verified.get('num_floors')} floor(s)\n"
                    f"  └─ 🧱 Verified Outer wall material: {qa_verified.get('outer_wall', {}).get('material')}")
        
    logger.info(f"----------------------------------------------------------------------\n"
                f"✅ [{session_id}] COMPLETED: INTERRUPT NODE (Resumed & verified)\n"
                f"======================================================================")
    return {
        "current_step": "qa_completed",
        "progress_pct": 50,
        "status": "calculating"
    }

