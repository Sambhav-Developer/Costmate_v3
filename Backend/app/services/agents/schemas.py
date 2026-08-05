from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class ConfidenceScore(BaseModel):
    mark_ocr: float
    wall_association: float

class DoorInstance(BaseModel):
    mark: str
    sheet_id: str
    floor_no: int
    bbox: List[float] # [x, y, w, h] or [ymin, xmin, ymax, xmax]
    wall_id: str
    wall_type: str
    wall_thickness: str
    int_ext: str
    opening_mode: str
    excluded: bool
    confidence: ConfidenceScore

from pydantic import BaseModel, Field, ConfigDict

class ScheduleData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    mark: str
    needs_review: bool = False
