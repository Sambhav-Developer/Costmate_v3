from app.services.graph.state import CostmateState
from app.core.logging import logger

def steel_quantities_node(state: CostmateState) -> dict:
    session_id = state.get("session_id", "unknown")
    logger.info(f"\n======================================================================\n"
                f"🚀 [{session_id}] STARTING: STEEL QUANTITIES NODE\n"
                f"----------------------------------------------------------------------\n"
                f"  ├─ 🕒 Estimating reinforcing steel tonnage per structural member...")
    
    qa = state.get("qa_verified") or state.get("qa_prefilled") or {}
    
    num_floors = qa.get("num_floors", 1)
    standard_floor_height = qa.get("floor_height_m", 3.0)
    slab_thickness = qa.get("slab_thickness_m", 0.12)
    foundation_depth = qa.get("foundation_depth_m", 1.5)
    
    # 1. Gather floor area
    floors = qa.get("floors", [])
    total_floor_area = 0.0
    total_perimeter = 0.0
    for floor in floors:
        rooms = floor.get("rooms", [])
        for room in rooms:
            length = room.get("length_m", 0.0)
            width = room.get("width_m", 0.0)
            total_floor_area += length * width
            total_perimeter += 2 * (length + width)
            
    if total_floor_area == 0:
        total_floor_area = 120.0 * num_floors
        total_perimeter = 50.0 * num_floors
        
    avg_floor_footprint = total_floor_area / num_floors
    avg_perimeter_per_floor = total_perimeter / num_floors

    # 2. Slabs Steel Estimation (0.8% of concrete volume typical = ~63 kg/cum)
    # Density of steel = 7850 kg/m3
    slab_concrete_vol = avg_floor_footprint * num_floors * slab_thickness
    # ~75 kg of steel per cubic meter of concrete in slabs
    slab_steel_kg = slab_concrete_vol * 75.0

    # 3. Columns Steel Estimation (~140 kg of steel per cubic meter of concrete)
    columns = qa.get("columns", [])
    columns_concrete_vol = 0.0
    for col in columns:
        col_width = col.get("width_m", 0.3)
        col_depth = col.get("depth_m", 0.3)
        count = col.get("count", 1)
        term_floor = col.get("termination_floor", num_floors)
        col_height = foundation_depth + (standard_floor_height * term_floor)
        columns_concrete_vol += count * col_width * col_depth * col_height
        
    column_steel_kg = columns_concrete_vol * 140.0

    # 4. Beams Steel Estimation (~120 kg of steel per cubic meter of concrete)
    beams_concrete_vol = 0.0
    beams = qa.get("beams", [])
    for beam in beams:
        b_w = beam.get("width_m", 0.23)
        b_d = beam.get("depth_m", 0.45)
        group_length = avg_perimeter_per_floor * num_floors * 0.8
        beams_concrete_vol += group_length * b_w * b_d
        
    if not beams:
        beams_concrete_vol = (avg_perimeter_per_floor * 1.2) * num_floors * 0.23 * 0.45
        
    beam_steel_kg = beams_concrete_vol * 120.0

    # 5. Footings Steel Estimation (~70 kg of steel per cubic meter of concrete)
    footings_concrete_vol = 0.0
    for col in columns:
        col_width = col.get("width_m", 0.3)
        col_depth = col.get("depth_m", 0.3)
        count = col.get("count", 1)
        footings_concrete_vol += count * (col_width + 0.4) * (col_depth + 0.4) * 0.3
        
    footing_steel_kg = footings_concrete_vol * 70.0

    # 6. Sum and Convert to metric tonnes (1 tonne = 1000 kg)
    footing_steel_tonnes = footing_steel_kg / 1000.0
    column_steel_tonnes = column_steel_kg / 1000.0
    beam_steel_tonnes = beam_steel_kg / 1000.0
    slab_steel_tonnes = slab_steel_kg / 1000.0
    
    total_steel_tonnes = footing_steel_tonnes + column_steel_tonnes + beam_steel_tonnes + slab_steel_tonnes

    result = {
        "steel_quantities": {
            "footing_steel_tonnes": round(footing_steel_tonnes, 3),
            "column_steel_tonnes": round(column_steel_tonnes, 3),
            "beam_steel_tonnes": round(beam_steel_tonnes, 3),
            "slab_steel_tonnes": round(slab_steel_tonnes, 3),
            "total_steel_tonnes": round(total_steel_tonnes, 3)
        }
    }
    
    logger.info(f"----------------------------------------------------------------------\n"
                f"✅ [{session_id}] COMPLETED: STEEL QUANTITIES NODE\n"
                f"  ├─ 🕒 Status: Success\n"
                f"  ├─ ◽ Footings Steel: {result['steel_quantities']['footing_steel_tonnes']} Tonnes\n"
                f"  ├─ 🏛️ Columns Steel: {result['steel_quantities']['column_steel_tonnes']} Tonnes\n"
                f"  ├─ ◽ Beams Steel: {result['steel_quantities']['beam_steel_tonnes']} Tonnes\n"
                f"  ├─ ◽ Slabs Steel: {result['steel_quantities']['slab_steel_tonnes']} Tonnes\n"
                f"  └─ 📈 Total Steel Reinforcement: {result['steel_quantities']['total_steel_tonnes']} Tonnes\n"
                f"======================================================================")
    return result
