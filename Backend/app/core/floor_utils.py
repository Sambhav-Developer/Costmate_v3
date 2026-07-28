"""
Floor name normalization utilities for Costmate AI.

Rule: "Stilt Floor" is treated as "Ground Floor" in all processing.
Stilt floors in Indian construction terminology refer to the ground-level
pillar/parking level — which IS the ground floor for estimation purposes.
"""

# Canonical floor name mapping: any of these → "Ground Floor"
_STILT_ALIASES = {
    "stilt",
    "stilt floor",
    "stilt floor plan",
    "ground stilt",
    "stilt/ground",
    "ground/stilt",
    "stilt (ground)",
    "ground (stilt)",
    "parking floor",
    "parking level",
    "pillar floor",
    "piloti floor",
}


def normalize_floor_name(name: str) -> str:
    """
    Normalizes a floor name so that any variation of 'Stilt' is treated
    as 'Ground Floor'.

    Examples:
        "Stilt Floor"       → "Ground Floor"
        "STILT FLOOR PLAN"  → "Ground Floor"
        "Stilt"             → "Ground Floor"
        "First Floor"       → "First Floor"  (unchanged)
        "Ground Floor"      → "Ground Floor" (unchanged)
    """
    if not name:
        return name
    stripped = name.strip()
    lower = stripped.lower()

    # Direct alias match
    if lower in _STILT_ALIASES:
        return "Ground Floor"

    # Partial match: name starts with "stilt" (e.g. "Stilt Floor Plan")
    if lower.startswith("stilt"):
        return "Ground Floor"

    return stripped


def normalize_floor(floor_dict: dict) -> dict:
    """
    Applies normalize_floor_name() to the 'floor_name' key of a floor dict
    in-place and returns the same dict.
    """
    if "floor_name" in floor_dict:
        floor_dict["floor_name"] = normalize_floor_name(floor_dict["floor_name"])
    return floor_dict


def normalize_room(room_dict: dict) -> dict:
    """
    Applies normalize_floor_name() to the 'floor_name' key of a room dict
    in-place and returns the same dict.
    """
    if "floor_name" in room_dict:
        room_dict["floor_name"] = normalize_floor_name(room_dict["floor_name"])
    return room_dict


def normalize_element(element_dict: dict) -> dict:
    """
    Applies normalize_floor_name() to the 'floor_name' key of a structural
    element dict (columns, beams, staircases, midlandings, etc.)
    in-place and returns the same dict.
    """
    if "floor_name" in element_dict:
        element_dict["floor_name"] = normalize_floor_name(element_dict["floor_name"])
    return element_dict
