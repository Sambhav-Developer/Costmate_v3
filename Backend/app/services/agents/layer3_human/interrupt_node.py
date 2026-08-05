from app.services.graph.state import CostmateState
from app.core.logging import logger

async def interrupt_node(state: CostmateState) -> dict:
    unresolved_queue = state.get("unresolved_queue", [])
    
    if unresolved_queue:
        logger.info(f"Interrupt Node: Pausing graph execution. Waiting for human review on {len(unresolved_queue)} items.")
        return {"status": "paused_qa", "current_step": "human_review_pending"}
    
    logger.info("Interrupt Node: No unresolved items found. Bypassing human review.")
    return {"status": "processing", "current_step": "human_review_bypassed"}
