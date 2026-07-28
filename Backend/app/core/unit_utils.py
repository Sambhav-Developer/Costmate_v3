import re

def parse_imperial_to_meters(imperial_str: str) -> float:
    """
    Parses an imperial string like "3'-0\"", "3'", or "1 3/4\"" and converts to meters.
    1 foot = 0.3048 meters
    1 inch = 0.0254 meters
    """
    if not imperial_str or not isinstance(imperial_str, str):
        return 0.0
        
    feet = 0.0
    inches = 0.0
    
    # Extract feet
    feet_match = re.search(r"(\d+(?:\.\d+)?)\s*'", imperial_str)
    if feet_match:
        feet = float(feet_match.group(1))
        
    # Extract inches. Examples: "1 3/4\"", "5\"", "1/2\""
    # We remove the feet part first to avoid confusing numbers
    inches_part = re.sub(r"(\d+(?:\.\d+)?)\s*'", "", imperial_str)
    
    # Try to find fractional inches like "1 3/4" or just "5" or "1/2"
    inch_match = re.search(r"(\d+)?\s*(?:(\d+)/(\d+))?\s*\"", inches_part)
    if inch_match:
        whole = inch_match.group(1)
        num = inch_match.group(2)
        den = inch_match.group(3)
        
        if whole:
            inches += float(whole)
        if num and den and float(den) != 0:
            inches += float(num) / float(den)
            
    return round((feet * 0.3048) + (inches * 0.0254), 4)
