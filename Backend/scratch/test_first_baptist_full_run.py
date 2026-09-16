import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import cv_detector_node
from app.services.agents.layer3_human.reconciliation_node import reconciliation_node

async def test_first_baptist():
    plan_pdf = os.path.abspath("../Assets/FIRST BAPTIS HIGH SCHOOL/Original_Plan.pdf")
    sched_pdf = os.path.abspath("../Assets/FIRST BAPTIS HIGH SCHOOL/Raw_Schedule.pdf")
    
    print(f"Testing First Baptist High School project:")
    print(f"  Plan: {plan_pdf}")
    print(f"  Schedule: {sched_pdf}")

    # Build exact schedule items matching Raw_Schedule.pdf
    schedule_marks = ["100A", "101A", "102A", "103A", "104A", "104B", "105A", "105B", "106A", "107A", "107B", 
                      "110A", "110B", "110C", "111A", "112A", "113A", "114A", "115A", "116A", "117A", "118A", "121A"]
    
    schedule_data = []
    pair_marks = {"100A", "106A", "110B", "110C"}
    for m in schedule_marks:
        item = {
            "mark": m,
            "DOOR PANEL 1 TYPE": "PNL-FG-AL" if m in pair_marks else ("PNL-FG-WD" if "A" in m else "PNL-F-HM"),
            "DOOR PANEL 1 WIDTH": "3'-0\"",
            "DOOR HEIGHT": "7'-0\"",
            "FRAME TYPE": "FRM-00AL(CW)" if m in pair_marks else ("FRM-CONCEALED" if m in ["105A", "107A"] else "FRM-00HM1"),
            "HARDWARE GROUP NO": "11.0",
            "LOCATION": "OFFICE 101"
        }
        if m in pair_marks:
            item["DOOR PANEL 2 TYPE"] = "PNL-FG-AL"
            item["DOOR PANEL 2 WIDTH"] = "3'-0\""

        schedule_data.append(item)

    state = {
        "intake_data": {
            "floors": [{"rawUrl": plan_pdf, "name": "Ground Floor", "page": 0}],
            "schedules": [{"rawUrl": sched_pdf, "name": "Door Schedule"}]
        },
        "schedule_data": schedule_data,
        "cv_results": {},
        "ocr_results": {}
    }

    # Step 2: Run CV Detector Node
    print("\n--- Running CV Detector Node ---")
    cv_res = await cv_detector_node(state)
    state["cv_results"] = cv_res.get("cv_results", {})
    recon_res = await reconciliation_node(state)
    doors = recon_res.get("bifurcated_schedule") or recon_res.get("qa_prefilled", {}).get("doors", [])
    
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
    asyncio.run(test_first_baptist())
