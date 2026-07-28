from typing import TypedDict, List, Dict, Any, Optional

class CostmateState(TypedDict):
    # Session Details
    session_id: str
    uploaded_file_path: str
    original_filename: str
    uploaded_page_paths: List[str]    # Paths to each rendered page image
    status: str                       # "uploading", "processing", "paused_qa", "calculating", "completed", "failed"
    current_step: str
    progress_pct: int
    
    # Project Onboarding Wizard Settings
    project_name: Optional[str]
    swarm_goal: Optional[str]         # "complete_estimate", "structural_only", "finishes_only"
    rate_schedule: Optional[str]       # "cpwd_2024", "pwd_state", etc.
    intake_data: Optional[Dict[str, Any]] # Floor-wise guided intake form answers

    # OCR & Spatial Analysis
    raw_ocr_text: str
    parsed_image_data: Dict[str, Any]
    
    # Layer 2 Vision Sub-Agents Output
    floor_plan: Dict[str, Any]         # rooms, floors, layout footprint
    dimensions: Dict[str, Any]         # L x W x H per room/element
    elements: Dict[str, Any]           # columns, beams, doors, windows, stairs
    
    # Human-in-the-Loop Q&A (18 Questions)
    qa_prefilled: Dict[str, Any]       # AI-suggested answers
    qa_verified: Dict[str, Any]        # User-submitted answers
    
    # Calculation Output
    civil_quantities: Dict[str, Any]   # Civil quantity takeoff: Excavation, Concrete, Brickwork, Plaster, Tiles, etc.
    
    # Validation & Artifact Generation
    validation_results: Dict[str, Any]
    validation_passed: bool
    excel_file_path: Optional[str]
    error: Optional[str]
    chat_history: Optional[List[Dict[str, Any]]]



    # V2.0 Doors & Windows Pipeline
    schedule_registry: Optional[Dict[str, Any]]
    plan_extractions: Optional[Dict[str, Any]] # Keyed by building_id
    reconciliation_result: Optional[Dict[str, Any]]
