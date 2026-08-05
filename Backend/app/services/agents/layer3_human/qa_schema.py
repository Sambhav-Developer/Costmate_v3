from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class RoomDoorSpec(BaseModel):
    width_m: float = Field(0.9, description="Width of the door in meters")
    height_m: float = Field(2.1, description="Height of the door in meters")
    material: str = Field("Teak Wood", description="Door shutter material (e.g. Flush Door, Teak Wood, PVC)")
    frame_type: str = Field("Teak Wood", description="Door frame type")
    count: int = Field(1, description="Number of identical doors in this room")

class RoomWindowSpec(BaseModel):
    width_m: float = Field(1.2, description="Width of the window in meters")
    height_m: float = Field(1.5, description="Height of the window in meters")
    material: str = Field("UPVC", description="Window frame/glass material (e.g. Aluminium, UPVC, Steel)")
    has_grill_or_gate: str = Field("Grill", description="Grill or channel gate present")
    has_seal_jam: bool = Field(True, description="Seal & Jam plaster/stone required")
    seal_jam_width_m: float = Field(0.15, description="Seal & Jam projection width in meters")
    count: int = Field(1, description="Number of windows in this room")

class RoomSpecSchema(BaseModel):
    name: str = Field(..., description="e.g. Bedroom 1, Kitchen, Toilet 1, Living Room, Front Balcony")
    type: str = Field("Room", description="Category of space")
    is_regular: bool = Field(True, description="Regular or Non-regular geometry")
    length_m: float = Field(..., description="Length dimension (internal clear)")
    width_m: float = Field(..., description="Width dimension (internal clear)")
    height_m: float = Field(3.0, description="Clear ceiling height")
    
    # Finishes
    tiles_enabled: bool = Field(True, description="Flooring tiles Y/N")
    tiles_type: str = Field("Normal tiles", description="Tile flooring type")
    pup_fall_ceiling: bool = Field(False, description="POP Fall Ceiling work Y/N")
    skirting_height_m: float = Field(0.1, description="Skirting tiles height")
    dado_height_m: float = Field(2.1, description="Wall dado tiling height (kitchen/toilet only)")
    
    # Openings & Railings
    doors: List[RoomDoorSpec] = Field(default_factory=list, description="Doors on this room walls")
    windows: List[RoomWindowSpec] = Field(default_factory=list, description="Windows on this room walls")
    railing_length_m: Optional[float] = Field(None, description="Length of railing for stairs or balcony")
    railing_material: str = Field("None", description="Railing material")

class StaircaseSpec(BaseModel):
    step_count: int = Field(18, description="Number of riser steps")
    tread_m: float = Field(0.25, description="Horizontal tread size in meters")
    rise_m: float = Field(0.15, description="Vertical rise height in meters")
    tread_material: str = Field("Granite", description="Tread finish material")
    rise_material: str = Field("Granite", description="Riser finish material")
    material: Optional[str] = Field("Granite", description="Steps stone finish material (legacy)")

class MidlandingSpec(BaseModel):
    length_m: float = Field(2.1, description="Length of midlanding slab in meters")
    width_m: float = Field(1.05, description="Width of midlanding slab in meters")
    material: str = Field("Granite", description="Midlanding stone finish material")

class FloorSpecSchema(BaseModel):
    floor_number: int = Field(..., description="0 for Ground, 1 for First etc.")
    floor_name: str = Field(..., description="Name of floor")
    rooms: List[RoomSpecSchema] = Field(default_factory=list, description="Room wise details list")
    staircase: Optional[StaircaseSpec] = Field(None, description="Staircase on this floor level")
    midlanding: Optional[MidlandingSpec] = Field(None, description="Midlanding slab on this floor level")
    
    # Floor replication rules
    copy_to_other_floors: bool = Field(False, description="Copy this layout to other floors")
    target_floors: List[int] = Field(default_factory=list, description="Target floor indices to replicate to")

class FootingSpec(BaseModel):
    name: str = Field("F1", description="Footing code code")
    width_m: float = Field(1.2, description="Footing width in meters")
    length_m: float = Field(1.2, description="Footing length in meters")
    depth_m: float = Field(0.4, description="Footing concrete thickness depth in meters")
    excavation_depth_m: float = Field(1.5, description="Total excavation depth from ground in meters")
    count: int = Field(1, description="Total footing count of this size")

class ColumnSpec(BaseModel):
    name: str = Field("C1", description="Column code")
    width_m: float = Field(0.23, description="Column width in meters")
    depth_m: float = Field(0.45, description="Column depth in meters")
    shape: Literal["Rectangle", "Circular", "Non-regular"] = Field("Rectangle", description="Shape of column")
    termination_floor: int = Field(1, description="Highest floor level this column group terminates")
    count: int = Field(1, description="Number of columns in this group")

class BeamSpec(BaseModel):
    name: str = Field("B1", description="Beam code")
    width_m: float = Field(0.23, description="Beam width in meters")
    depth_m: float = Field(0.45, description="Beam depth in meters")
    length_m: float = Field(4.5, description="Average beam span length in meters")
    count: int = Field(1, description="Number of beams in this group")

class QASchema(BaseModel):
    # --- Project Metadata ---
    project_name: Optional[str] = Field("Estimate of Building", description="Project / Name of Work")
    sub_work_name: Optional[str] = Field("Building Work", description="Name of Sub Work")
    raw_ocr_text: Optional[str] = Field("", description="Raw OCR Text extracted from drawing")

    # --- Basics & Global Settings ---
    plan_type: Literal["Residential", "Commercial", "Mixed-Use", "Industrial"] = Field("Residential")
    num_floors: int = Field(1, ge=1)
    has_basement: bool = Field(False)
    num_basements: int = Field(0)
    floor_height_m: float = Field(3.0)
    
    # --- Global Structural Schedules ---
    footings: List[FootingSpec] = Field(default_factory=list, description="Footings size schedule")
    columns: List[ColumnSpec] = Field(default_factory=list, description="Columns size schedule")
    beams: List[BeamSpec] = Field(default_factory=list, description="Beams size schedule")
    
    # --- Floor Wise Details ---
    floors: List[FloorSpecSchema] = Field(default_factory=list, description="Floor details list")
    
    model_config = {"extra": "allow"}
