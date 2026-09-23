import os
import sys
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer1_schedule.schedule_parser_node import schedule_parser_node

async def test_poole_sched():
    sched_a = os.path.abspath("../Assets/POOLE HUFFMAN/Schedule_A.pdf")
    sched_b = os.path.abspath("../Assets/POOLE HUFFMAN/Schedule_B.pdf")
    
    state = {
        "intake_data": {
            "schedules": [
                {"name": "Schedule A", "rawUrl": sched_a},
                {"name": "Schedule B", "rawUrl": sched_b}
            ]
        }
    }
    
    res = await schedule_parser_node(state)
    doors = res.get("qa_verified", {}).get("doors", [])
    print(f"Extracted {len(doors)} doors from Poole Huffman schedule files:")
    for d in doors:
        print("  Mark:", d.get("mark"), "| Door:", d.get("door_type"), "| Frame:", d.get("frame_type"), "| Hardware:", d.get("hardware_group_no"))

if __name__ == "__main__":
    asyncio.run(test_poole_sched())
