import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import cv_detector_node
from app.services.agents.layer3_human.reconciliation_node import reconciliation_node

async def main():
    plan_a = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
    plan_b = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")
    sched_marks = ["94", "98A", "98B", "98C", "99A", "100B", "105", "71", "72", "73", "76", "77", "90", "97"]
    schedule_data = []
    for m in sched_marks:
        hw = "SET 8" if m == "99A" else ("SET 6" if m in ["98B", "90", "97"] else "SET 9")
        item = {
            "mark": m,
            "DOOR TYPE": "CO" if m in ["98C", "100B"] else "A",
            "WIDTH": "3'-0\"",
            "HEIGHT": "8'-4\"",
            "DOOR MATERIAL": "SCWD",
            "FRAME TYPE": "KD" if m in ["94", "98A", "98B", "100B", "90", "97"] else "EX",
            "FRAME MATERIAL": "HM" if m in ["94", "98A", "98B", "100B", "90", "97"] else "EX",
            "HARDWARE GROUP NO": hw
        }
        schedule_data.append(item)
        
    state = {
        "intake_data": {"floors": [{"name": "Plan A", "rawUrl": plan_a}, {"name": "Plan B", "rawUrl": plan_b}]},
        "schedule_data": schedule_data
    }
    cv_res = await cv_detector_node(state)
    state["cv_results"] = cv_res.get("cv_results", {})
    res = await reconciliation_node(state)
    
    doors = res.get("bifurcated_schedule") or res.get("qa_prefilled", {}).get("doors", [])
    print(f"\n================ 3-LAYER CLASSIFICATION BREAKDOWN ({len(doors)} items) ================")
    print(f"{'MARK':5s} | {'L1 SCHEDULE':12s} | {'L2 VECTOR':10s} | {'L3 VLM':10s} | {'FINAL':8s} | {'REVIEW'}")
    print("-" * 75)
    for r in doors:
        m = r.get("type") or r.get("mark")
        l1 = r.get("layer1_schedule_mode")
        l2 = r.get("layer2_vector_mode")
        l3 = r.get("layer3_vlm_mode")
        fin = r.get("final_reconciled_mode") or r.get("_reconciled_opening_mode")
        rev = "CHECK" if r.get("needs_review") else "OK"
        print(f"{m:5s} | {str(l1):12s} | {str(l2):10s} | {str(l3):10s} | {str(fin):8s} | {rev}")

if __name__ == "__main__":
    asyncio.run(main())
