import sys
import os
sys.path.append(os.path.abspath("."))
import json
from sqlalchemy import text
from app.db.postgres import engine

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, state FROM estimation_sessions WHERE id = '404a20e9-108c-45b9-a364-0b657de975bc'"))
        row = result.fetchone()
        if not row:
            result = conn.execute(text("SELECT id, state FROM estimation_sessions ORDER BY updated_at DESC LIMIT 1"))
            row = result.fetchone()
            
        if row:
            sid, state = row
            if isinstance(state, str):
                state = json.loads(state)
            print(f'=== Session ID: {sid} ===')
            intake = state.get('intake_data', {})
            gSettings = intake.get('globalSettings', {})
            print('=== gSettings Keys ===', list(gSettings.keys()))
            print('=== unitMatrix ===', json.dumps(gSettings.get('unitMatrix'), indent=2))
            print('=== unitMixMatrix ===', json.dumps(gSettings.get('unitMixMatrix'), indent=2))
            print('=== unitDoorSchedule ===', json.dumps(gSettings.get('unitDoorSchedule'), indent=2))
            print('=== scheduleRegistry ===', json.dumps(gSettings.get('scheduleRegistry'), indent=2))
        else:
            print('No sessions found in DB')
except Exception as e:
    print('DB Error:', e)
