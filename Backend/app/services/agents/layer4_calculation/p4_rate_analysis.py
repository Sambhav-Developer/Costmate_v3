from app.services.graph.state import CostmateState
from app.core.logging import logger

def rate_analysis_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: RATE ANALYSIS NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 🕒 Multiplying quantities with escalated rates and summing totals...")
    
    # 1. Fetch data from previous steps
    civil_q = state.get("civil_quantities") or {}
    steel_q = state.get("steel_quantities") or {}
    dsr_rates = state.get("dsr_rates") or {}
    
    # Quantities
    excavation_qty = civil_q.get("excavation_volume_cum", 0.0)
    pcc_qty = civil_q.get("pcc_volume_cum", 0.0)
    rcc_qty = civil_q.get("rcc_volume_cum", 0.0)
    brick_qty = civil_q.get("brickwork_volume_cum", 0.0)
    plaster_qty = civil_q.get("plaster_area_sqm", 0.0)
    floor_qty = civil_q.get("flooring_area_sqm", 0.0)
    steel_qty = steel_q.get("total_steel_tonnes", 0.0)
    
    # Mapped Rates (default to base if mapping has issues)
    excavation_rate = dsr_rates.get("2.8", {}).get("escalated_rate", 180.50)
    pcc_rate = dsr_rates.get("5.2", {}).get("escalated_rate", 4850.00)
    rcc_rate = dsr_rates.get("5.9", {}).get("escalated_rate", 6750.00)
    steel_rate = dsr_rates.get("5.22", {}).get("escalated_rate", 62000.00)
    brick_rate = dsr_rates.get("6.4", {}).get("escalated_rate", 5400.00)
    plaster_rate = dsr_rates.get("13.1", {}).get("escalated_rate", 210.00)
    floor_rate = dsr_rates.get("11.38", {}).get("escalated_rate", 950.00)
    
    # 2. Compute Itemized Costs
    excavation_cost = excavation_qty * excavation_rate
    pcc_cost = pcc_qty * pcc_rate
    rcc_cost = rcc_qty * rcc_rate
    steel_cost = steel_qty * steel_rate
    brick_cost = brick_qty * brick_rate
    plaster_cost = plaster_qty * plaster_rate
    floor_cost = floor_qty * floor_rate
    
    # Group costs
    civil_total = excavation_cost + pcc_cost + rcc_cost + brick_cost
    steel_total = steel_cost
    finishing_total = plaster_cost + floor_cost
    
    # Subtotal
    subtotal = civil_total + steel_total + finishing_total
    
    # GST (18%)
    gst_amount = subtotal * 0.18
    
    # Grand Total
    grand_total = subtotal + gst_amount
    
    # 3. Assemble analysis payload
    rate_analysis = {
        "item_costs": {
            "2.8": round(excavation_cost, 2),
            "5.2": round(pcc_cost, 2),
            "5.9": round(rcc_cost, 2),
            "5.22": round(steel_cost, 2),
            "6.4": round(brick_cost, 2),
            "13.1": round(plaster_cost, 2),
            "11.38": round(floor_cost, 2)
        },
        "group_totals": {
            "civil_works": round(civil_total, 2),
            "steel_reinforcement": round(steel_total, 2),
            "finishing_works": round(finishing_total, 2)
        },
        "subtotal": round(subtotal, 2),
        "gst_amount": round(gst_amount, 2),
        "grand_total": round(grand_total, 2)
    }
    
    logger.info(f"----------------------------------------------------------------------\n"
                f"✅ [{session_id}] COMPLETED: RATE ANALYSIS NODE\n"
                f"  ├─ 🕒 Status: Success\n"
                f"  ├─ 🧱 Civil Works Cost: INR {rate_analysis['group_totals']['civil_works']}\n"
                f"  ├─ 🏗️ Steel Cost: INR {rate_analysis['group_totals']['steel_reinforcement']}\n"
                f"  ├─ 🏁 Finishing Works Cost: INR {rate_analysis['group_totals']['finishing_works']}\n"
                f"  ├─ 💵 Subtotal: INR {rate_analysis['subtotal']}\n"
                f"  ├─ 💰 GST (18%): INR {rate_analysis['gst_amount']}\n"
                f"  └─ 📈 GRAND TOTAL: INR {rate_analysis['grand_total']}\n"
                f"======================================================================")
    return {
        "rate_analysis": rate_analysis
    }
