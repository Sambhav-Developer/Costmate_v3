import os
import sys
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer1_intake.schedule_extractor_node import schedule_extractor_node
from app.services.agents.layer2_vision.cv_detector_node import cv_detector_node
from app.services.agents.layer3_reconciliation.reconciliation_node import reconciliation_node

async def run_full():
    plan_a = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
    plan_b = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")
    sched_a = os.path.abspath("../Assets/POOLE HUFFMAN/Schedule_A.pdf")
    sched_b = os.path.abspath("../Assets/POOLE HUFFMAN/Schedule_B.pdf")
    
    state = {
        "intake_data": {
            "schedules": [
                {"name": "Schedule A", "rawUrl": sched_a},
                {"name": "Schedule B", "rawUrl": sched_b}
            ],
            "floors": [
                {"name": "Plan A", "rawUrl": plan_a},
                {"name": "Plan B", "rawUrl": plan_b}
            ]
        }
    }
    
    print("--- 1. Running Schedule Extractor ---")
    s_res = await schedule_extractor_node(state)
    state.update(s_res)
    sched_doors = state.get("qa_verified", {}).get("doors", [])
    print(f"Schedule doors extracted: {len(sched_doors)}")
    for d in sched_doors:
        print(" ", d)
        
    print("\n--- 2. Running CV Detector Node ---")
    cv_res = await cv_detector_node(state)
    state.update(cv_res)
    cv_dets = state.get("cv_results", {}).get("detections", [])
    print(f"CV detections found: {len(cv_dets)}")
    for d in cv_dets[:20]:
        print(f"  mark={d.get('mark')} floor={d.get('floor_name')} cx={d.get('w_cx'):.1f} cy={d.get('w_cy'):.1f} is_orphan={d.get('is_orphan_plan_tag')}")

    print("\n--- 3. Running Reconciliation Node ---")
    rec_res = await reconciliation_node(state)
    state.update(rec_res)
    takeoff = state.get("takeoff_table", [])
    print(f"\nFINAL TAKEOFF TABLE ({len(takeoff)} items):")
    for item in takeoff:
        print(" ", item)

if __name__ == "__main__":
    asyncio.run(run_full())
