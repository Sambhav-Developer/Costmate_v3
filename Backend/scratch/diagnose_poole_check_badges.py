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
    for r in res.get("reconciled_items", []):
        m = r.get("type") or r.get("mark")
        if m in ["99A", "97"]:
            print(f"\n================ MARK {m} ================")
            print(f"  needs_review = {r.get('needs_review')}")
            print(f"  review_reason = {r.get('review_reason')}")
            print(f"  is_borderline = {r.get('is_borderline')}")
            print(f"  Takeoff Notes = {r.get('Takeoff Notes')}")
            print(f"  RECONCILED OPENING MODE = {r.get('RECONCILED OPENING MODE')}")

    print("\n================ UNRESOLVED QUEUE ================")
    for u in state.get("unresolved_queue", []):
        print(f"  {u}")

if __name__ == "__main__":
    asyncio.run(main())
