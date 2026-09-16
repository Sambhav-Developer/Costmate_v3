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

    # Step 1: Parse Schedule
    state = {
        "intake_data": {
            "floors": [{"rawUrl": plan_pdf, "name": "Ground Floor", "page": 0}],
            "schedules": [{"rawUrl": sched_pdf, "name": "Door Schedule"}]
        },
        "schedule_data": [],
        "cv_results": {},
        "ocr_results": {}
    }

    # Run schedule parser or mock schedule items if needed
    try:
        from fitz import open as fitz_open
        doc = fitz_open(sched_pdf)
        print(f"Schedule PDF loaded with {len(doc)} pages.")
    except Exception as e:
        print(f"Error reading schedule PDF: {e}")

    # Build schedule items for 100A to 121A
    schedule_marks = ["100A", "101A", "102A", "103A", "104A", "104B", "105A", "105B", "106A", "107A", "107B", 
                      "110A", "110B", "110C", "111A", "112A", "113A", "114A", "115A", "116A", "117A", "118A", "121A"]
    
    schedule_data = []
    for m in schedule_marks:
        item = {
            "mark": m,
            "DOOR PANEL 1 TYPE": "PNL FG WD" if "A" in m else "PNL F HM",
            "DOOR PANEL 1 WIDTH": "3'-0\"",
            "DOOR HEIGHT": "7'-0\"",
            "FRAME TYPE": "FRM-00AL(CW)" if m in ["100A", "106A", "110B", "110C"] else ("FRM-CONCEALED" if m in ["105A", "107A"] else "FRM-00HM1"),
            "HARDWARE GROUP NO": "11.0",
            "LOCATION": "OFFICE 101"
        }
        schedule_data.append(item)

    state["schedule_data"] = schedule_data

    # Step 2: Run CV Detector Node
    print("\n--- Running CV Detector Node ---")
    try:
        cv_res = await cv_detector_node(state)
        detections = cv_res.get("cv_results", {}).get("detections", [])
        print(f"CV Detector returned results. Total detections: {len(detections)}")
    except Exception as e:
        import traceback
        print(f"CV Detector exception: {e}")
        traceback.print_exc()
        detections = []
    detected_marks = set()
    for d in detections:
        m = d.get("mark")
        detected_marks.add(m)
        bbox = d.get("bbox")
        attached = d.get("is_attached")
        print(f"  Detected mark '{m}' at {bbox} (Attached={attached})")

    missing = set(schedule_marks) - detected_marks
    print(f"\nMissing marks from detection: {missing} (Total missing: {len(missing)})")

    # Step 3: Run Reconciliation Node
    state["cv_results"] = cv_res.get("cv_results", {})
    recon_res = await reconciliation_node(state)
    recon_items = recon_res.get("reconciled_items", [])
    
    print(f"\n--- Reconciliation Results ({len(recon_items)} items) ---")
    check_count = 0
    ok_count = 0
    for r in recon_items:
        m = r.get("mark")
        needs_rev = r.get("needs_review")
        mode = r.get("Opening Mode")
        int_ext = r.get("INT/EXT")
        notes = r.get("Takeoff Notes", "")
        if needs_rev:
            check_count += 1
            status = "CHECK"
        else:
            ok_count += 1
            status = "OK"
        print(f"  Mark {m:5s} | Status: {status:5s} | Mode: {mode:10s} | INT/EXT: {int_ext:12s} | Notes: {notes}")

    print(f"\nSummary: Total OK = {ok_count}/{len(schedule_marks)}, Total CHECK = {check_count}/{len(schedule_marks)}")

if __name__ == "__main__":
    asyncio.run(test_first_baptist())
