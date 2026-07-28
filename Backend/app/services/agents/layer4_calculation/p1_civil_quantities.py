from app.services.graph.state import CostmateState
from app.core.logging import logger

def civil_quantities_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"[{session_id}] Civil quantities skipped (Tracking only doors and windows)")
    
    return {
        "civil_quantities": {
            "excavation_volume_cum": 0.0,
            "pcc_volume_cum": 0.0,
            "rcc_volume_cum": 0.0,
            "brickwork_volume_cum": 0.0,
            "plaster_area_sqm": 0.0,
            "flooring_area_sqm": 0.0
        }
    }
