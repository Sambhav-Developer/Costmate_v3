import asyncio
import sys
import json
import os
sys.path.append(os.path.abspath('.'))

from app.services.agents.layer1_schedule.schedule_parser import schedule_parser_agent

async def main():
    url = "https://res.cloudinary.com/dnu6r5kgn/image/upload/v1785309272/Costmate/Rohit%203/8dbd77e6-b146-49bc-b67f-7201caf6f864_schedule.png"
    results = await schedule_parser_agent.process_schedule([url])
    
    with open("schedule_result.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
