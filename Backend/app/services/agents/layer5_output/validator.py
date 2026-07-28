from app.services.graph.state import CostmateState
from app.core.logging import logger

def validator_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: VALIDATOR NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 🕒 Performing sanity checks on quantity calculations...")
    
    civil_q = state.get("civil_quantities") or {}
    
    checks = []
    validation_passed = True
    
    # Check 1: Civil Quantities Positive
    excavation = civil_q.get("excavation_volume_cum", 0.0)
    pcc = civil_q.get("pcc_volume_cum", 0.0)
    rcc = civil_q.get("rcc_volume_cum", 0.0)
    brickwork = civil_q.get("brickwork_volume_cum", 0.0)
    
    civil_positive = excavation > 0 and pcc > 0 and rcc > 0 and brickwork > 0
    checks.append({
        "name": "civil_quantities_positive",
        "passed": civil_positive,
        "detail": f"Excavation: {excavation} cum, PCC: {pcc} cum, RCC: {rcc} cum, Brickwork: {brickwork} cum"
    })
    if not civil_positive:
        validation_passed = False
        
    # Compile results
    validation_results = {
        "passed": validation_passed,
        "checks": checks
    }
    
    logger.info(f"----------------------------------------------------------------------\n"
                f"✅ [{session_id}] COMPLETED: VALIDATOR NODE\n"
                f"  ├─ 🕒 Status: Success\n"
                f"  ├─ 🔍 Validation Passed: {validation_passed}\n"
                f"  └─ 📋 Check Results:")
    for chk in checks:
        status_emoji = "✅" if chk['passed'] else "❌"
        logger.info(f"     ├─ {status_emoji} [{chk['name']}] detail: {chk['detail']}")
    logger.info(f"======================================================================")
    return {
        "validation_passed": validation_passed,
        "validation_results": validation_results
    }
