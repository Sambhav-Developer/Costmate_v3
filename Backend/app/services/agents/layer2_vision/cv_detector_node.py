import json
from app.core.openrouter_client import openrouter_client
from app.services.graph.state import CostmateState
from app.core.logging import logger

async def cv_detector_node(state: CostmateState) -> dict:
    logger.info("CV Detector: Analyzing floor plan for doors, OPENING MODE, and INT/EXT contexts...")
    image_paths = state.get("uploaded_page_paths", [])
    if not image_paths:
        return {"cv_results": []}
        
    prompt = """
    You are an advanced Computer Vision architectural model analyzing a floor plan.
    Detect all doors and windows. For each, output:
    1. mark: The exact door/window mark found next to it (e.g. D-1, W-1, RS012).
    2. opening_mode: Analyze the architectural swing symbol. Is it SGL (Single), DBL (Double), or CO (Cased Opening)?
    3. int_ext: Analyze the wall context it is placed in. Is it INT (Interior wall) or EXT (Exterior wall)?
    
    Output MUST be a JSON array of objects under the key 'detections'.
    Example: {"detections": [{"mark": "D-1", "opening_mode": "SGL", "int_ext": "INT"}]}
    """
    
    res = await openrouter_client.generate_chat(prompt=prompt, image_paths=image_paths, json_mode=True, temperature=0.1)
    
    try:
        data = json.loads(res)
        detections = data.get("detections", [])
        return {"cv_results": {"detections": detections}}
    except Exception as e:
        logger.error(f"CV Detector Parse Error: {e}")
        return {"cv_results": {"detections": []}}
