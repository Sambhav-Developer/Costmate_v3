import json
import re
from datetime import datetime, timezone
from app.services.graph.graph import costmate_graph
from app.services.graph.session_manager import session_manager
from app.core.openrouter_client import openrouter_client, parse_json_response
from app.core.logging import logger
from app.core.exceptions import NotFoundException
from app.modules.chat.schemas import ChatMessageSchema

class ChatService:
    async def process_chat(self, session_id: str, user_id: int, payload: ChatMessageSchema) -> dict:
        logger.info(f"[{session_id}] Received AI Copilot chat message from user: {payload.message}")

        restored = await session_manager.restore_session_if_needed(session_id, user_id=user_id)
        if not restored:
            logger.warning(f"[{session_id}] Session not found or expired for user.")
            raise NotFoundException("Session not found or expired.")
            
        config = {"configurable": {"thread_id": session_id}}
        
        try:
            state_snapshot = await costmate_graph.aget_state(config)
            values = state_snapshot.values or {}
            
            current_qa = values.get("qa_verified") or values.get("qa_prefilled") or {}
            
            prompt = f"""
You are the AI Swarm Copilot for Costmate AI.
Analyze the user's message and check if they want to modify, refine, or add any estimation specifications/parameters.

Current Project Specifications (JSON):
{json.dumps(current_qa, indent=2)}

User Message:
"{payload.message}"

Goal:
1. Identify if the user wants to update any parameters in the project specifications.
2. If they do:
   - Convert any standard structural/civil changes to metric units (e.g. 9 inches = 0.23m).
   - Set "has_updates" to true.
   - Do NOT output the entire JSON. Instead, provide a list of updates.
   - Each update MUST have an "action" ("set", "append", or "delete"), a "path" (a list of keys/indices to reach the field), and a "value" (for set/append).
     Example (Update): {{"action": "set", "path": ["floors", 0, "rooms", 0, "doors", 0, "frame_type"], "value": "Teak Wood"}}
     Example (Add to array): {{"action": "append", "path": ["floors", 0, "rooms", 0, "doors"], "value": {{"width_m": 0.9, "height_m": 2.1, "count": 1}}}}
     Example (Delete item): {{"action": "delete", "path": ["floors", 0, "rooms", 2]}}
3. If they don't (just general conversation, query, or greeting):
   - Set "has_updates" to false.
   - Set "updates" to [].
4. Output a helpful assistant response explaining what was updated, or answer their question if there was no parameter change, in "ai_response".

Return STRICTLY a JSON object with this structure:
{{
  "ai_response": "Polite response to user",
  "has_updates": true|false,
  "updates": [
    {{
      "action": "set",
      "path": ["key1", 0, "key2"],
      "value": "new value"
    }}
  ]
}}
"""
            response_text = await openrouter_client.generate_chat(prompt, json_mode=True)
            parsed = parse_json_response(response_text)
            ai_response = parsed.get("ai_response", "I could not process that request.")
            has_updates = parsed.get("has_updates", False)
            updates_list = parsed.get("updates", [])
            
            if has_updates and updates_list:
                updated_qa = json.loads(json.dumps(current_qa))
                # Apply deep updates
                for update in updates_list:
                    action = update.get("action", "set")
                    path = update.get("path", [])
                    value = update.get("value")
                    if not path: continue
                    
                    target = updated_qa
                    for key in path[:-1]:
                        target = target[key]
                        
                    last_key = path[-1]
                    if action == "delete":
                        if isinstance(target, list) and isinstance(last_key, int):
                            target.pop(last_key)
                        elif isinstance(target, dict) and last_key in target:
                            del target[last_key]
                    elif action == "append":
                        if isinstance(target[last_key], list):
                            target[last_key].append(value)
                    else: # set
                        target[last_key] = value
            else:
                updated_qa = None

            
        except Exception as e:
            logger.warning(f"[{session_id}] OpenRouter is offline or returned an error: {e}. Running local rule-based fallback...")
            
            ai_response = ""
            has_updates = False
            updated_qa = None
            message_lower = payload.message.lower()
            
            wall_match = re.search(r'(?:wall\s+thickness|outer\s+wall)\s+(?:to|is)\s+([\d\.]+)\s*(inch|inches|mm|m)?', message_lower)
            if wall_match:
                val = float(wall_match.group(1))
                unit = wall_match.group(2) or "m"
                if "inch" in unit:
                    val_m = round(val * 0.0254, 3)
                    unit_label = f"{val} inches"
                elif "mm" in unit:
                    val_m = round(val / 1000.0, 3)
                    unit_label = f"{val} mm"
                else:
                    val_m = val
                    unit_label = f"{val} meters"
                    
                updated_qa = json.loads(json.dumps(current_qa))
                if "outer_wall" not in updated_qa:
                    updated_qa["outer_wall"] = {}
                updated_qa["outer_wall"]["thickness_m"] = val_m
                has_updates = True
                ai_response = f"I've updated the outer wall thickness to {unit_label} ({val_m}m) locally and triggered a recalculation workflow."

            elif re.search(r'floor\s+height\s+(?:to|is)\s+([\d\.]+)\s*(m|ft|feet|foot)?', message_lower):
                match = re.search(r'floor\s+height\s+(?:to|is)\s+([\d\.]+)\s*(m|ft|feet|foot)?', message_lower)
                val = float(match.group(1))
                unit = match.group(2) or "m"
                if "ft" in unit or "feet" in unit or "foot" in unit:
                    val_m = round(val * 0.3048, 2)
                    unit_label = f"{val} feet"
                else:
                    val_m = val
                    unit_label = f"{val}m"
                    
                updated_qa = json.loads(json.dumps(current_qa))
                updated_qa["floor_height_m"] = val_m
                has_updates = True
                ai_response = f"I've set the standard floor height to {unit_label} ({val_m}m) locally and triggered a recalculation workflow."

            elif re.search(r'(?:footing|foundation)\s+depth\s+(?:to|is)\s+([\d\.]+)\s*(m|ft|feet)?', message_lower):
                match = re.search(r'(?:footing|foundation)\s+depth\s+(?:to|is)\s+([\d\.]+)\s*(m|ft|feet)?', message_lower)
                val = float(match.group(1))
                unit = match.group(2) or "m"
                if "ft" in unit or "feet" in unit:
                    val_m = round(val * 0.3048, 2)
                    unit_label = f"{val} feet"
                else:
                    val_m = val
                    unit_label = f"{val}m"
                    
                updated_qa = json.loads(json.dumps(current_qa))
                updated_qa["foundation_depth_m"] = val_m
                has_updates = True
                ai_response = f"I've set the foundation/footing depth to {unit_label} ({val_m}m) locally and triggered a recalculation workflow."

            elif re.search(r'(?:number\s+of\s+floors|num\s+floors|floors\s+count)\s+(?:to|is)\s+(\d+)', message_lower):
                match = re.search(r'(?:number\s+of\s+floors|num\s+floors|floors\s+count)\s+(?:to|is)\s+(\d+)', message_lower)
                val = int(match.group(1))
                
                updated_qa = json.loads(json.dumps(current_qa))
                updated_qa["num_floors"] = val
                has_updates = True
                ai_response = f"I've set the number of floors to {val} locally and triggered a recalculation workflow."

            elif "exca" in message_lower:
                civil_quantities = values.get("civil_quantities") or {}
                volume = civil_quantities.get("excavation_volume_cum")
                if volume is not None:
                    ai_response = f"The total excavation quantity calculated for this project is {volume} Cubic Metres (cum)."
                else:
                    ai_response = "I couldn't find the excavation quantity because calculations haven't run yet. Please verify parameters to start the calculation swarm."

            elif "plast" in message_lower:
                civil_quantities = values.get("civil_quantities") or {}
                area = civil_quantities.get("plaster_area_sqm")
                if area is not None:
                    ai_response = f"The calculated plaster area for this project is {area} Square Metres (sqm)."
                else:
                    ai_response = "I couldn't find the plaster area because calculations haven't run yet."

            elif "floor" in message_lower or "tile" in message_lower:
                civil_quantities = values.get("civil_quantities") or {}
                area = civil_quantities.get("flooring_area_sqm")
                if area is not None:
                    ai_response = f"The calculated flooring area is {area} Square Metres (sqm)."
                else:
                    ai_response = "I couldn't find the flooring area because calculations haven't run yet."

            elif "concr" in message_lower or "rcc" in message_lower:
                civil_quantities = values.get("civil_quantities") or {}
                volume = civil_quantities.get("rcc_volume_cum")
                if volume is not None:
                    ai_response = f"The calculated RCC (concrete) volume is {volume} Cubic Metres (cum)."
                else:
                    ai_response = "I couldn't find the concrete volume because calculations haven't run yet."

            else:
                ai_response = (
                    "The OpenRouter service appears to be offline. I've activated local rule-based fallback. "
                    "You can ask me to adjust parameters (e.g. wall thickness, floor height, footing depth) or query computed values (e.g. excavation, concrete, plaster). "
                    "Ensure OpenRouter is reachable (`ollama serve`) to enable full AI agent conversation."
                )
        
        chat_history = values.get("chat_history") or []
        if not isinstance(chat_history, list):
            chat_history = []
            
        user_entry = {
            "role": "user",
            "message": payload.message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        ai_entry = {
            "role": "assistant",
            "message": ai_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        updated_chat_history = chat_history + [user_entry, ai_entry]
        
        await costmate_graph.aupdate_state(config, {"chat_history": updated_chat_history}, as_node="interrupt_node")
        
        if has_updates and updated_qa:
            logger.info(f"[{session_id}] Chat instruction updated QA parameters. Awaiting manual recalculation.")
            await costmate_graph.aupdate_state(config, {"qa_prefilled": updated_qa, "qa_verified": None}, as_node="interrupt_node")
            
        state_snapshot = await costmate_graph.aget_state(config)
        if state_snapshot.values:
            session_manager._save_to_db(session_id, state_snapshot.values, user_id)
                
        return {
            "ai_response": ai_response,
            "has_updates": has_updates,
            "chat_history": updated_chat_history
        }

chat_service = ChatService()
