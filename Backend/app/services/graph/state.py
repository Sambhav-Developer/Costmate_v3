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
    ocr_results: Optional[Dict[str, Any]]            # Results of OCR1, OCR2, OCR3 consensus
    cv_results: Optional[Dict[str, Any]]             # Output of OpenCV / mark detection including auto-derived INT/EXT and OPENING MODE
    
    # Reconciliation & Human-in-the-loop
    unresolved_queue: Optional[List[Dict[str, Any]]] # Discrepancies between plan and schedule
    human_resolutions: Optional[Dict[str, Any]]      # User's submitted answers
    qa_prefilled: Optional[Dict[str, Any]]
    qa_verified: Optional[Dict[str, Any]]
    
    # Final Processed Data
    fused_schedule: Optional[List[Dict[str, Any]]]   # The final accurate list of doors/windows
    
    # Layer 5: Output Artifacts
    excel_file_path: Optional[str]
    annotated_pdf_path: Optional[str]
    error: Optional[str]
