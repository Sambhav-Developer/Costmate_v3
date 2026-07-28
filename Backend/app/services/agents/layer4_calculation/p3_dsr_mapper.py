from app.services.graph.state import CostmateState
from app.core.logging import logger
from app.services.dsr.dsr_loader import dsr_loader

def dsr_mapper_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: DSR MAPPER NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 🕒 Fetching DSR base rates and calculating floor-wise escalation...")
    
    qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
    num_floors = qa.get("num_floors", 1)
    
    # Mapped item codes
    item_mapping = {
        "excavation": "2.8",
        "pcc": "5.2",
        "rcc": "5.9",
        "steel": "5.22",
        "brickwork": "6.4",
        "plastering": "13.1",
        "flooring": "11.38"
    }
    
    dsr_rates = {}
    from app.services.dsr.floor_escalation import get_floor_escalation_pct
    
    for item_name, code in item_mapping.items():
        # Retrieve base item
        base_item = dsr_loader.get_dsr_item(code)
        if not base_item:
            logger.warning(f"Could not map code {code} for item {item_name}")
            continue
            
        base_rate = base_item.get("rate", 0.0)
        description = base_item.get("description", "")
        
        # Customize flooring rate & description based on selected tiles_type
        if item_name == "flooring":
            tiles_type = qa.get("tiles_type", "Normal tiles")
            if tiles_type == "Marble":
                base_rate = 1500.00
                description = "Providing and laying Marble flooring of specified size including cement mortar base, jointing with slurry and matching pigment pointing etc. complete."
            elif tiles_type == "Granite":
                base_rate = 1800.00
                description = "Providing and laying Granite flooring of specified size including cement mortar base, jointing with slurry and matching pigment pointing etc. complete."
        
        # Calculate average rate across all floors
        if item_name in ["excavation", "pcc"]:
            # Excavation & PCC happen only at Plinth level (Floor 1)
            escalation_pct = get_floor_escalation_pct(1)
            escalated_rate = round(base_rate * (1 + (escalation_pct / 100.0)), 2)
            applied_escalation_pct = 0.0
        else:
            # Average rate across all floors
            total_escalated_rate = 0.0
            for fl in range(1, num_floors + 1):
                escalation_pct = get_floor_escalation_pct(fl)
                total_escalated_rate += base_rate * (1 + (escalation_pct / 100.0))
            escalated_rate = round(total_escalated_rate / num_floors, 2)
            
            # Derived escalation percentage
            if base_rate > 0:
                applied_escalation_pct = round(((escalated_rate - base_rate) / base_rate) * 100.0, 2)
            else:
                applied_escalation_pct = 0.0
                
        dsr_rates[code] = {
            "item_name": item_name,
            "description": description,
            "unit": base_item.get("unit", ""),
            "base_rate": base_rate,
            "escalated_rate": escalated_rate,
            "applied_escalation_pct": applied_escalation_pct
        }
        
    logger.info(f"----------------------------------------------------------------------\n"
                f"✅ [{session_id}] COMPLETED: DSR MAPPER NODE\n"
                f"  ├─ 🕒 Status: Success\n"
                f"  ├─ 📊 Mapped item count: {len(dsr_rates)} items\n"
                f"  └─ 💵 Rates summary:")
    for code, info in dsr_rates.items():
        logger.info(f"     ├─ [{code}] {info['item_name']}: Base INR {info['base_rate']} -> Escalated INR {info['escalated_rate']} (+{info['applied_escalation_pct']}%)")
    logger.info(f"======================================================================")
    return {
        "dsr_rates": dsr_rates
    }
