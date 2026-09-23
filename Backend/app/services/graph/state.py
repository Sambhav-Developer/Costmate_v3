from typing import TypedDict, List, Dict, Any, Optional

class CostmateState(TypedDict):
    # Session Details
    session_id: str
    uploaded_file_path: str
    original_filename: str
    uploaded_page_paths: List[str]    # Paths to floor plan images
    status: str
    current_step: str
    progress_pct: int
    
    # Project Settings
    project_name: Optional[str]
    intake_data: Optional[Dict[str, Any]]
    
    # Layer 1 & 2: Track A, B, C Outputs
    schedule_data: Optional[List[Dict[str, Any]]]    # JSON array of the extracted schedule
    schedule_sections: Optional[Dict[str, List[Dict[str, Any]]]] # Structured: unique_doors, repeating_doors, overhead_doors, cased_openings, windows
    ocr_results: Optional[Dict[str, Any]]            # Results of OCR1, OCR2, OCR3 consensus
    cv_results: Optional[Dict[str, Any]]             # Output of OpenCV / mark detection including auto-derived INT/EXT and OPENING MODE

    # Multifamily Matrix & Bifurcation Engine
    building_type: Optional[str]                     # MULTI_FAMILY or NON_MULTI_FAMILY
    unit_mix_matrix: Optional[List[Dict[str, Any]]]  # Building x Floor x Unit Type matrix
    unit_door_schedule: Optional[List[Dict[str, Any]]] # Parsed REPEATING unit doors catalog
    unit_door_matrix: Optional[List[Dict[str, Any]]] # Unit Type x Door Tag extended matrix
    bifurcated_schedule: Optional[List[Dict[str, Any]]] # Schedule items after wall-type/location bifurcation
    
    # Reconciliation & Human-in-the-loop
    unresolved_queue: Optional[List[Dict[str, Any]]] # Discrepancies between plan and schedule
    human_resolutions: Optional[Dict[str, Any]]      # User's submitted answers
    qa_prefilled: Optional[Dict[str, Any]]
    qa_verified: Optional[Dict[str, Any]]
    qa_gates_status: Optional[Dict[str, Any]]        # Status of QA Gates 1-9
    
    # Final Processed Data
    fused_schedule: Optional[List[Dict[str, Any]]]   # The final accurate list of doors/windows
    
    # Layer 5: Output Artifacts
    excel_file_path: Optional[str]
    annotated_pdf_path: Optional[str]
    error: Optional[str]
    specifications_text: Optional[str] # Extracted specifications/scope text from DOCX/Word files
    specifications_insights: Optional[Dict[str, Any]] # Structured specifications/scope insights



