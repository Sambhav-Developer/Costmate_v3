import os
import uuid
import json
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from typing import List, Dict, Any
from app.dependencies import get_current_user
from app.config import settings
from app.services.graph.session_manager import session_manager
from app.core.logging import logger
from app.core.cloud import upload_to_cloudinary
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.core.prompts import (
    SCHEDULE_INGESTION_PROMPT,
    DRAWING_CLASSIFIER_PROMPT,
    DOORS_WINDOWS_EXTRACTOR_PROMPT,
    RECONCILIATION_PROMPT
)

v2_router = APIRouter(prefix="/api/v2/doors-windows", tags=["Doors & Windows V2"])

@v2_router.post("/session")
async def create_v2_session(current_user: dict = Depends(get_current_user)):
    """Create a fresh session tailored for the V2 Doors & Windows pipeline."""
    session_id = str(uuid.uuid4())
    session_manager.start_session(
        session_id=session_id,
        uploaded_file_path="",
        uploaded_page_paths=[],
        original_filename="v2_pipeline",
        user_id=current_user["id"],
        project_name="Doors & Windows Extract",
    )
    # Initialize state fields
    session_manager.update_state(session_id, {
        "schedule_files": [], # List of schedule Cloudinary URLs
        "plan_files": [],     # List of plan Cloudinary URLs
        "schedule_registry": None,
        "plan_extractions": {},
        "reconciliation_result": None,
        "v2_status": "draft"  # draft, processing, completed, error
    })
    return {"session_id": session_id, "status": "created"}

async def _save_and_upload(session_id: str, file: UploadFile) -> str:
    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{session_id}_{uuid.uuid4().hex[:6]}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    cloud_url = upload_to_cloudinary(file_path, resource_type="raw" if ext == ".pdf" else "image") or file_path
    return cloud_url

@v2_router.post("/{session_id}/schedule")
async def upload_schedule(session_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Stage 1: Just upload and save the schedule file."""
    restored = await session_manager.restore_session_if_needed(session_id, user_id=current_user["id"])
    if not restored:
        raise HTTPException(status_code=404, detail="Session not found")
        
    cloud_url = await _save_and_upload(session_id, file)
    
    state = session_manager.get_state(session_id)
    schedule_files = state.get("schedule_files", [])
    schedule_files.append(cloud_url)
    session_manager.update_state(session_id, {"schedule_files": schedule_files})
    
    return {"status": "success", "file_url": cloud_url}

@v2_router.post("/{session_id}/plan")
async def upload_plan(session_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Stage 2: Just upload and save the floor plan file."""
    restored = await session_manager.restore_session_if_needed(session_id, user_id=current_user["id"])
    if not restored:
        raise HTTPException(status_code=404, detail="Session not found")
        
    cloud_url = await _save_and_upload(session_id, file)
    
    state = session_manager.get_state(session_id)
    plan_files = state.get("plan_files", [])
    plan_files.append(cloud_url)
    session_manager.update_state(session_id, {"plan_files": plan_files})
    
    return {"status": "success", "file_url": cloud_url}


async def _run_v2_pipeline(session_id: str):
    """Background task to run the full V2 pipeline."""
    try:
        session_manager.update_state(session_id, {"v2_status": "processing"})
        state = session_manager.get_state(session_id)
        schedule_files = state.get("schedule_files", [])
        plan_files = state.get("plan_files", [])
        
        # 1. Schedule Ingestion
        registry = None
        if schedule_files:
            logger.info(f"[{session_id}] Running Schedule Ingestion...")
            res_text = await openrouter_client.generate_chat(
                prompt=SCHEDULE_INGESTION_PROMPT,
                image_paths=schedule_files, # Note: if multiple, pass all to LLM
                json_mode=True
            )
            registry = parse_json_response(res_text)
            session_manager.update_state(session_id, {"schedule_registry": registry})
            
        # 2. Plan Extraction
        plan_extractions = {}
        for plan_url in plan_files:
            logger.info(f"[{session_id}] Classifying plan {plan_url}...")
            # Classifier
            class_text = await openrouter_client.generate_chat(
                prompt=DRAWING_CLASSIFIER_PROMPT,
                image_paths=[plan_url],
                json_mode=True
            )
            classification = parse_json_response(class_text)
            
            if classification.get("drawing_category") != "NOT_APPLICABLE":
                logger.info(f"[{session_id}] Extracting plan {plan_url}...")
                context_prompt = DOORS_WINDOWS_EXTRACTOR_PROMPT
                if registry:
                    context_prompt = f"SCHEDULE REGISTRY INGESTED FROM STAGE 1:\n{json.dumps(registry, indent=2)}\n\n{DOORS_WINDOWS_EXTRACTOR_PROMPT}"
                
                extract_text = await openrouter_client.generate_chat(
                    prompt=context_prompt,
                    image_paths=[plan_url],
                    json_mode=True
                )
                extraction = parse_json_response(extract_text)
                building_id = extraction.get("building_id", "unspecified")
                if building_id not in plan_extractions:
                    plan_extractions[building_id] = []
                plan_extractions[building_id].append(extraction)
        
        session_manager.update_state(session_id, {"plan_extractions": plan_extractions})
        
        # 3. Reconciliation
        logger.info(f"[{session_id}] Running Reconciliation...")
        recon_prompt = RECONCILIATION_PROMPT
        recon_context = f"SCHEDULE REGISTRY:\n{json.dumps(registry)}\n\nPLAN EXTRACTIONS:\n{json.dumps(plan_extractions)}\n\n{recon_prompt}"
        
        recon_text = await openrouter_client.generate_chat(
            prompt=recon_context,
            image_paths=[],
            json_mode=True
        )
        reconciliation = parse_json_response(recon_text)
        session_manager.update_state(session_id, {
            "reconciliation_result": reconciliation,
            "v2_status": "completed"
        })
        logger.info(f"[{session_id}] V2 Pipeline completed successfully.")
        
    except Exception as e:
        logger.error(f"[{session_id}] V2 Pipeline failed: {e}")
        session_manager.update_state(session_id, {"v2_status": "error", "error": str(e)})


@v2_router.post("/{session_id}/process")
async def start_processing(session_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Stage 3: Triggers final processing in the background."""
    restored = await session_manager.restore_session_if_needed(session_id, user_id=current_user["id"])
    if not restored:
        raise HTTPException(status_code=404, detail="Session not found")
        
    state = session_manager.get_state(session_id)
    if not state.get("plan_files"):
        raise HTTPException(status_code=400, detail="No plan files uploaded. Cannot start processing.")
        
    background_tasks.add_task(_run_v2_pipeline, session_id)
    return {"status": "processing_started"}

@v2_router.get("/{session_id}/status")
async def get_v2_status(session_id: str, current_user: dict = Depends(get_current_user)):
    """Poll for pipeline status and results."""
    restored = await session_manager.restore_session_if_needed(session_id, user_id=current_user["id"])
    if not restored:
        raise HTTPException(status_code=404, detail="Session not found")
        
    state = session_manager.get_state(session_id)
    return {
        "status": state.get("v2_status"),
        "schedule_files_count": len(state.get("schedule_files", [])),
        "plan_files_count": len(state.get("plan_files", [])),
        "schedule_registry": state.get("schedule_registry"),
        "plan_extractions": state.get("plan_extractions"),
        "reconciliation_result": state.get("reconciliation_result"),
        "error": state.get("error")
    }
