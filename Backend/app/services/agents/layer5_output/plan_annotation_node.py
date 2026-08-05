import os
from app.core.logging import logger
from app.services.graph.state import CostmateState
from app.config import settings

async def plan_annotation_node(state: CostmateState) -> dict:
    logger.info("Plan Annotation Node: Color-coding door marks on PDF...")
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed. Cannot annotate PDF.")
        return {"current_step": "annotation_failed", "error": "PyMuPDF missing"}
        
    uploaded_file = state.get("uploaded_file_path")
    if not uploaded_file or not os.path.exists(uploaded_file):
        logger.warning("No raw PDF found to annotate.")
        return {}
        
    schedule_data = state.get("schedule_data", [])
    cv_results = state.get("cv_results", {})
    detections = cv_results.get("detections", [])
    
    # Create lookups
    sched_lookup = {str(item.get("mark", "")).strip().upper(): item for item in schedule_data if item.get("mark")}
    cv_lookup = {str(d.get("mark", "")).strip().upper(): d for d in detections if d.get("mark")}
    
    # Color definitions (RGB in 0-1 range for fitz)
    color_interior = (1.0, 1.0, 0.0) # Yellow
    color_exterior = (0.0, 0.0, 1.0) # Blue
    color_storefront = (1.0, 0.75, 0.8) # Pink
    
    try:
        doc = fitz.open(uploaded_file)
        
        for page in doc:
            for mark in cv_lookup.keys():
                cv_info = cv_lookup.get(mark, {})
                sched_info = sched_lookup.get(mark, {})
                
                material = str(sched_info.get("MATERIAL", "")).upper()
                int_ext = str(cv_info.get("int_ext", "")).upper()
                
                # Determine color logic
                if "ALUMINUM" in material or "GLASS" in material or "ALUMINIUM" in material:
                    highlight_color = color_storefront
                elif int_ext == "EXT":
                    highlight_color = color_exterior
                else:
                    highlight_color = color_interior # Default to interior
                    
                # Search for text on page to highlight
                text_instances = page.search_for(mark)
                for inst in text_instances:
                    # Draw a semi-transparent rectangle highlight over the mark
                    annot = page.add_rect_annot(inst)
                    annot.set_colors(stroke=highlight_color, fill=highlight_color)
                    annot.set_opacity(0.4)
                    annot.update()
                    
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        out_path = os.path.join(settings.OUTPUT_DIR, f"{state.get('session_id', 'output')}_annotated.pdf")
        doc.save(out_path)
        doc.close()
        
        logger.info(f"Annotated PDF saved at {out_path}")
        return {"annotated_pdf_path": out_path}
        
    except Exception as e:
        logger.error(f"Error during PDF annotation: {e}")
        return {"error": str(e)}
