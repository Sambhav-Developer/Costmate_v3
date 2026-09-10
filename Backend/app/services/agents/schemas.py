from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any

class ConfidenceScore(BaseModel):
    mark_ocr: float
    wall_association: float

class DoorInstance(BaseModel):
    mark: str
    sheet_id: str
    floor_no: int
    bbox: List[float] # [x, y, w, h] or [ymin, xmin, ymax, xmax]
    wall_id: str = ""
    wall_type: str = "DRY"
    wall_thickness: str = ""
    int_ext: str = "Interior" # Interior, Exterior, Soft Exterior, Window, Not in Scope
    opening_mode: str = "Single" # Single, Pair, By-Pass, Bi-Fold, Dbl-Pocket, Overhead, Cased
    excluded: bool = False
    exclusion_reason: str = ""
    confidence: ConfidenceScore = Field(default_factory=lambda: ConfidenceScore(mark_ocr=1.0, wall_association=1.0))

class DoorScheduleItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    
    qty: int = 1
    number: str = Field(alias="mark") # Door Tag / Number
    location: str = ""
    opening_mode: str = "Single" # Single, Pair, By-Pass, Bi-Fold, Dbl-Pocket, Overhead, Cased
    int_ext: str = "Interior" # Interior, Exterior, Soft Exterior, Window, Not in Scope
    wall_type: str = "DRY"
    takeoff_notes: str = ""
    width: str = ""
    height: str = ""
    thickness: str = ""
    door_type: str = ""
    door_material: str = ""
    door_finish: str = ""
    frame_type: str = ""
    frame_material: str = ""
    frame_finish: str = ""
    head: str = ""
    jamb: str = ""
    sill: str = ""
    fire_rating: str = ""
    hardware_set: str = ""
    key_card_reader: str = "No"
    comments: str = ""
    
    # Section categorization
    section: str = "REPEATING" # UNIQUE, REPEATING, OVERHEAD, CASED, WINDOW
    is_bifurcated: bool = False
    original_tag: Optional[str] = None
    needs_review: bool = False

class UnitMixItem(BaseModel):
    building: str = "Building A"
    floor: str = "Level 1"
    unit_type: str = "A1"
    count: int = 0
    is_ada: bool = False

class ScheduleData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    mark: str
    needs_review: bool = False

