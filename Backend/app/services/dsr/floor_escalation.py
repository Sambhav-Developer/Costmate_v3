from app.core.logging import logger

def get_floor_escalation_pct(floor_number: int) -> float:
    """
    Calculates cost escalation percentage based on floor height/level.
    - Ground Floor (floor_number=1) has 0% base escalation.
    - Upper floors receive a compound or additive 1.5% escalation per floor
      due to lifting materials, safety measures, scaffolding, etc.
    - Basements (floor_number <= 0) receive a flat 5.0% escalation due to shoring/dewatering.
    """
    if floor_number <= 0:
        # Basement
        escalation = 5.0
    elif floor_number == 1:
        # Ground Floor
        escalation = 0.0
    else:
        # Upper Floors (e.g. floor 2 -> 1.5%, floor 3 -> 3.0%)
        escalation = (floor_number - 1) * 1.5
        
    logger.debug(f"Floor {floor_number} escalation percentage: {escalation}%")
    return escalation
