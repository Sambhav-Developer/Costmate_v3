import asyncio
import os
import sys
from dotenv import load_dotenv

# Add Backend folder to path and load env
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

from app.services.agents.layer1_schedule.schedule_parser import schedule_parser_agent

async def test():
    # Test Area A alone
    img_a = r"c:\Users\Hp\Desktop\Costmate_v3\Assets\Rohit Test Assets\Area A Door.png"
    print("=" * 60)
    print("Running process_schedule on Area A Door...")
    res_a = await schedule_parser_agent.process_schedule([img_a])
    print(f"\nArea A: Got {len(res_a)} rows")
    if res_a:
        print("Keys in first row:", list(res_a[0].keys()))
        import pprint
        pprint.pprint(res_a[:3])  # Print first 3 rows only to keep output concise

    print()
    
    # Test Area B alone
    img_b = r"c:\Users\Hp\Desktop\Costmate_v3\Assets\Rohit Test Assets\Area B Door.png"
    print("=" * 60)
    print("Running process_schedule on Area B Door...")
    res_b = await schedule_parser_agent.process_schedule([img_b])
    print(f"\nArea B: Got {len(res_b)} rows")
    if res_b:
        print("Keys in first row:", list(res_b[0].keys()))
        import pprint
        pprint.pprint(res_b[:3])  # Print first 3 rows only

    # Check key consistency between A and B
    if res_a and res_b:
        keys_a = set(res_a[0].keys())
        keys_b = set(res_b[0].keys())
        print("\n" + "=" * 60)
        print("Key consistency check:")
        print(f"  Area A keys: {sorted(keys_a)}")
        print(f"  Area B keys: {sorted(keys_b)}")
        diff_a = keys_a - keys_b
        diff_b = keys_b - keys_a
        if diff_a:
            print(f"  Keys ONLY in A (not in B): {sorted(diff_a)}")
        if diff_b:
            print(f"  Keys ONLY in B (not in A): {sorted(diff_b)}")
        if not diff_a and not diff_b:
            print("  ✓ PERFECT: Both schedules have identical keys!")

if __name__ == "__main__":
    asyncio.run(test())
