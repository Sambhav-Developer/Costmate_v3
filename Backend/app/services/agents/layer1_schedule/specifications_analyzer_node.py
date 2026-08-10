import json
from app.services.graph.state import CostmateState
from app.core.logging import logger
from app.core.openrouter_client import openrouter_client, parse_json_response

SPECIFICATIONS_ANALYZER_PROMPT = """
You are an expert construction specifications analyzer.
Analyze the following project specifications text and extract key takeoff insights.
Return a clean, structured JSON object with no explanations, no markdown fences, matching the schema below:

{
  "project_name": "string or null",
  "project_address": "string or null",
  "exclusions": ["list of explicit scope exclusions, e.g. 'Three openings with aluminium door material are excluded'"],
  "door_defaults": {
    "thickness": "string or null, e.g. '1-3/4\"'",
    "undercut": "string or null, e.g. '5/8 inch'",
    "material": "string or null, e.g. 'solid-core wood doors'",
    "frame_material": "string or null, e.g. 'hollow metal frames'"
  },
  "special_features": [
    "list of special hinges, hardware, double-acting doors, or acoustical/sound-rating wall requirements"
  ]
}

SPECIFICATIONS TEXT:
{specifications_text}
"""

async def specifications_analyzer_node(state: CostmateState) -> dict:
    logger.info("Specifications Analyzer Node: Analyzing Project Specifications...")
    spec_text = state.get("specifications_text", "")
    if not spec_text or not spec_text.strip():
        logger.info("Specifications Analyzer Node: No specifications text found.")
        return {"specifications_insights": {}}
        
    prompt = SPECIFICATIONS_ANALYZER_PROMPT.replace("{specifications_text}", spec_text)
    try:
        res_text = await openrouter_client.generate_chat(
            prompt=prompt,
            image_paths=[],
            json_mode=True,
            temperature=0.1
        )
        insights = parse_json_response(res_text)
        logger.info(f"Specifications Analyzer Node: Extracted insights successfully: {insights}")
        return {"specifications_insights": insights}
    except Exception as e:
        logger.error(f"Specifications Analyzer Node failed: {e}")
        return {"specifications_insights": {}}
