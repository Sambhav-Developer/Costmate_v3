import os
import sys
import asyncio
import fitz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import cv_detector_node

state = {
    "intake_data": {
        "floors": [
            {"name": "Plan A", "rawUrl": os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_A.pdf")},
            {"name": "Plan B", "rawUrl": os.path.abspath("../Assets/POOLE HUFFMAN/Original_Plan_B.pdf")}
        ]
    },
    "qa_verified": {
        "doors": [] # No Schedule table in Poole Huffman PDFs (only Hardware Specs)
    }
}

async def main():
    res = await cv_detector_node(state)
    cv_res = res.get("cv_results", {})
    detections = cv_res.get("detections", [])
    print(f"\n================ POOLE HUFFMAN RUN RESULTS ================")
    print(f"Total Detections: {len(detections)}")
    for d in detections:
        print(f"  Detected mark '{d.get('mark')}' on {d.get('floor_name')} at cx={d.get('w_cx'):.1f}, cy={d.get('w_cy'):.1f}")

if __name__ == "__main__":
    asyncio.run(main())
