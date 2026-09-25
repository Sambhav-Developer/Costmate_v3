path = r'C:\Users\Hp\Desktop\Costmate_v3\Backend\app\services\agents\layer2_vision\cv_detector_node.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update detect_double_egress
old_de = """def detect_double_egress(groups: list, mark_cx: float, mark_cy: float) -> bool:
    \"\"\"
    DE (08 Double Egress Door): Two arc groups swinging into OPPOSITE rooms.

    Geometric signature:
    - Two distinct arc groups present.
    - One arc group is on Side A of wall, the other arc group is on Side B of wall face.
    - For horizontal wall: arcs split above vs below mark_cy (y_spread >= x_spread).
    - For vertical wall: arcs split left vs right of mark_cx (x_spread > y_spread).
    - Requires cross-wall separation >= 25pt on dominant axis.
    \"\"\"
    if len(groups) < 2:
        return False

    centroids = []
    for g in groups:
        for arc in g:
            centroids.append((arc["cx"], arc["cy"]))

    if len(centroids) < 2:
        return False

    # For DE: arc groups are on OPPOSITE sides of the wall face (one swings into each room).
    # For PR: both arc groups are on the SAME side (both leaves swing into the same room, side by side).
    #
    # The key geometric discriminator:
    # - For a HORIZONTAL wall: DE arcs split across Y (above vs below mark_cy).
    #   PR arcs split across X (left vs right of opening center, SAME Y side).
    #
    # - For a VERTICAL wall: DE arcs split across X (left vs right of mark_cx).
    #   PR arcs split across Y (above vs below opening center, SAME X side).
    #
    # Single rule: DE fires ONLY when arcs are on opposite sides of the mark ON THE AXIS
    # where their spread is LARGER than on the OTHER axis.
    # This prevents PR (symmetric side-by-side on X/Y) from being mistaken for DE.
    #
    # Separation threshold: >= 25pt on the dominant axis is required (cross-wall distance).

    CROSS_WALL_MIN = 25.0  # min pts of cross-wall separation per side to confirm DE

    x_spread = max(c[0] for c in centroids) - min(c[0] for c in centroids)
    y_spread = max(c[1] for c in centroids) - min(c[1] for c in centroids)

    # Determine dominant axis (axis with largest arc spread).
    # For horizontal wall: dominant = Y. For vertical wall: dominant = X.
    # For PR: dominant axis is the opening-width axis (NOT the cross-wall axis).
    # For DE: dominant axis IS the cross-wall axis.

    if y_spread >= x_spread:
        # Y-dominant: candidate for horizontal wall DE
        above = [c for c in centroids if c[1] < mark_cy - CROSS_WALL_MIN]
        below  = [c for c in centroids if c[1] > mark_cy + CROSS_WALL_MIN]
        if above and below:
            logger.info(
                f"CV Drawing Analysis: DE (Double Egress) -- arc groups on opposite sides "
                f"(horizontal wall, y_spread={y_spread:.1f}pt >= x_spread={x_spread:.1f}pt)."
            )
            return True
    else:
        # X-dominant: candidate for vertical wall DE
        left_side  = [c for c in centroids if c[0] < mark_cx - CROSS_WALL_MIN]
        right_side = [c for c in centroids if c[0] > mark_cx + CROSS_WALL_MIN]
        if left_side and right_side:
            logger.info(
                f"CV Drawing Analysis: DE (Double Egress) -- arc groups on opposite sides "
                f"(vertical wall, x_spread={x_spread:.1f}pt > y_spread={y_spread:.1f}pt)."
            )
            return True

    return False"""

new_de = """def detect_double_egress(groups: list, mark_cx: float, mark_cy: float) -> bool:
    \"\"\"
    DE (08 Double Egress Door): Two arc groups swinging into OPPOSITE rooms.

    Geometric signature:
    - Two distinct arc groups present.
    - One arc is on Side A of wall face, other arc is on Side B of wall face.
    - Horizontal wall (wall line Y=mark_cy):
      - One arc has cy < mark_cy - CROSS_WALL_MIN and abs(cx - mark_cx) < 45pt
      - Other arc has cy > mark_cy + CROSS_WALL_MIN and abs(cx - mark_cx) < 45pt
    - Vertical wall (wall line X=mark_cx):
      - One arc has cx < mark_cx - CROSS_WALL_MIN and abs(cy - mark_cy) < 45pt
      - Other arc has cx > mark_cx + CROSS_WALL_MIN and abs(cy - mark_cy) < 45pt
    \"\"\"
    if len(groups) < 2:
        return False

    centroids = []
    for g in groups:
        for arc in g:
            centroids.append((arc["cx"], arc["cy"]))

    if len(centroids) < 2:
        return False

    CROSS_WALL_MIN = 25.0  # min pts cross-wall distance from centerline

    # Check horizontal wall DE: arcs split above and below mark_cy, BOTH near mark_cx
    above_h = [c for c in centroids if c[1] < mark_cy - CROSS_WALL_MIN and abs(c[0] - mark_cx) < 45.0]
    below_h = [c for c in centroids if c[1] > mark_cy + CROSS_WALL_MIN and abs(c[0] - mark_cx) < 45.0]
    if above_h and below_h:
        logger.info(
            f"CV Drawing Analysis: DE (Double Egress) -- horizontal wall: "
            f"arcs split above (cy<{mark_cy-CROSS_WALL_MIN:.1f}) and below (cy>{mark_cy+CROSS_WALL_MIN:.1f})."
        )
        return True

    # Check vertical wall DE: arcs split left and right of mark_cx, BOTH near mark_cy
    left_v  = [c for c in centroids if c[0] < mark_cx - CROSS_WALL_MIN and abs(c[1] - mark_cy) < 45.0]
    right_v = [c for c in centroids if c[0] > mark_cx + CROSS_WALL_MIN and abs(c[1] - mark_cy) < 45.0]
    if left_v and right_v:
        logger.info(
            f"CV Drawing Analysis: DE (Double Egress) -- vertical wall: "
            f"arcs split left (cx<{mark_cx-CROSS_WALL_MIN:.1f}) and right (cx>{mark_cx+CROSS_WALL_MIN:.1f})."
        )
        return True

    return False"""

assert old_de in content, "old_de not found!"
content = content.replace(old_de, new_de)

# 2. Fix storefront fallback in classify_opening_from_schedule
old_sf_tail = """    else:
        if is_sf_token(panel_a) or is_sf_token(panel_b):
            return "STOREFRONT"
        elif not panel_a and not panel_b:
            return "STOREFRONT"

    if w_a:
        return "SGL"

    return "UNKNOWN" """

# Let's search for exact tail of classify_opening_from_schedule
start_idx = content.find("def classify_opening_from_schedule")
end_idx = content.find("def detect_bypass")
sched_code = content[start_idx:end_idx]

old_tail_snippet = """    else:
        if is_sf_token(panel_a) or is_sf_token(panel_b):
            return "STOREFRONT"
        elif not panel_a and not panel_b:
            return "STOREFRONT"

    if w_a:
        return "SGL"

    return "UNKNOWN" """

new_tail_snippet = """    else:
        if is_sf_token(panel_a) or is_sf_token(panel_b):
            return "STOREFRONT"

    if w_a or any(p in dtype_upper for p in ["SINGLE", "SGL", "FLUSH", "1 LEAF", "DOOR"]) or dtype_upper in ["SGL", "SINGLE", ""]:
        return "SGL"

    return "SGL" """

assert old_tail_snippet in content, "old_tail_snippet not found!"
content = content.replace(old_tail_snippet, new_tail_snippet)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS")
