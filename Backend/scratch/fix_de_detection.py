path = r'C:\Users\Hp\Desktop\Costmate_v3\Backend\app\services\agents\layer2_vision\cv_detector_node.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_section = '''    # For DE, arc groups are on OPPOSITE sides of the wall face (cross-wall swing into each room).
    # For PR, both arc groups are on the SAME side of the wall (both swing into the same room).
    #
    # Detection strategy:
    # - Both axes (x_spread and y_spread) are computed between the arc group centroids.
    # - The axis with the LARGER spread is the "opening-width" axis (leaf A vs leaf B, side by side).
    # - The axis with the SMALLER spread is the "cross-wall" axis.
    # - DE fires when BOTH conditions hold:
    #     (a) The cross-wall axis has opposite-side separation >= CROSS_WALL_MIN (20pt).
    #     (b) The cross-wall spread is >= DOMINANT_RATIO (0.6x) of the opening-width spread,
    #         preventing a near-zero cross-wall from accidentally triggering DE.

    CROSS_WALL_MIN = 20.0    # min pts of cross-wall separation to claim arcs crossed the wall
    DOMINANT_RATIO = 0.6     # cross-wall spread must be >= 60% of opening-width spread

    x_spread = max(c[0] for c in centroids) - min(c[0] for c in centroids)
    y_spread = max(c[1] for c in centroids) - min(c[1] for c in centroids)

    # Horizontal wall: opening-width axis = X, cross-wall axis = Y.
    # DE: one arc above mark_cy by >= CROSS_WALL_MIN AND one arc below mark_cy by >= CROSS_WALL_MIN.
    # Additional guard: y_spread must be >= DOMINANT_RATIO * x_spread (cross-wall is significant).
    above = [c for c in centroids if c[1] < mark_cy - CROSS_WALL_MIN]
    below  = [c for c in centroids if c[1] > mark_cy + CROSS_WALL_MIN]
    if above and below and (x_spread == 0 or y_spread >= DOMINANT_RATIO * x_spread):
        logger.info(
            f"CV Drawing Analysis: DE (Double Egress) -- arc groups on opposite sides "
            f"(horizontal wall, y_spread={y_spread:.1f}pt, x_spread={x_spread:.1f}pt)."
        )
        return True

    # Vertical wall: opening-width axis = Y, cross-wall axis = X.
    # DE: one arc left of mark_cx by >= CROSS_WALL_MIN AND one arc right by >= CROSS_WALL_MIN.
    # Additional guard: x_spread must be >= DOMINANT_RATIO * y_spread (cross-wall is significant).
    left_side  = [c for c in centroids if c[0] < mark_cx - CROSS_WALL_MIN]
    right_side = [c for c in centroids if c[0] > mark_cx + CROSS_WALL_MIN]
    if left_side and right_side and (y_spread == 0 or x_spread >= DOMINANT_RATIO * y_spread):
        logger.info(
            f"CV Drawing Analysis: DE (Double Egress) -- arc groups on opposite sides "
            f"(vertical wall, x_spread={x_spread:.1f}pt, y_spread={y_spread:.1f}pt)."
        )
        return True

    return False'''

new_section = '''    # For DE: arc groups are on OPPOSITE sides of the wall face (one swings into each room).
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

    return False'''

if old_section in content:
    content = content.replace(old_section, new_section, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fix applied successfully')
else:
    print('ERROR: old_section not found')
    idx = content.find('# For DE, arc groups are on OPPOSITE sides')
    if idx >= 0:
        print(repr(content[idx:idx+300]))
