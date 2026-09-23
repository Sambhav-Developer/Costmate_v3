import os
import sys
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import cv_detector_node

async def run_test():
    plan_a = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")
    plan_b = os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")
    
    sched_marks = ["94", "98A", "98B", "98C", "99A", "100B", "105", "71", "72", "73", "76", "77", "90", "97"]
    doors = [{"mark": m, "door_type": "SCWD"} for m in sched_marks]
    
    state = {
        "intake_data": {
            "floors": [
                {"name": "Plan A", "rawUrl": plan_a},
                {"name": "Plan B", "rawUrl": plan_b}
            ]
        },
        "qa_verified": {
            "doors": doors
        }
    }
    
    res = await cv_detector_node(state)
    cv_res = res.get("cv_results", {})
    detections = cv_res.get("detections", [])
    print(f"\n================ CV DETECTOR DETECTIONS ({len(detections)}) ================")
    detected_marks = set()
    for d in detections:
        m = d.get('mark')
        detected_marks.add(m)
        print(f"  Mark '{m:6}' on {d.get('floor_name')} at cx={d.get('w_cx'):.1f}, cy={d.get('w_cy'):.1f}")

    print("\n================ MISSING SCHEDULE MARKS ================")
    for sm in sched_marks:
        if sm in detected_marks:
            print(f"  Mark '{sm:6}': DETECTED")
        else:
            print(f"  Mark '{sm:6}': MISSING")

if __name__ == "__main__":
    asyncio.run(run_test())
