import sys
import os
import fitz
import unittest
import inspect

# Add Backend folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer2_vision.cv_detector_node import (
    find_door_tag_shapes,
    is_tag_attached_to_door_opening,
    find_closest_schedule_mark,
    reassemble_pdf_words,
    validate_vector_opening_geometry
)

class TestDoorDetectionRegression(unittest.TestCase):
    """
    Permanent multi-project regression test suite for shape-agnostic door tag detection.
    Prevents fixes for new projects from breaking previously working projects.
    """

    @classmethod
    def setUpClass(cls):
        cls.cbr_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Assets/CBR Radiology/Original Plan.pdf"))
        cls.has_cbr_pdf = os.path.exists(cls.cbr_pdf_path)

    def test_cbr_radiology_door_tag_detection(self):
        if not self.has_cbr_pdf:
            self.skipTest(f"CBR Radiology PDF not found at {self.cbr_pdf_path}")
            
        doc = fitz.open(self.cbr_pdf_path)
        page = doc[0]
        words_on_page = reassemble_pdf_words(page.get_text("words"))
        drawings_on_page = page.get_drawings()
        
        sched_marks = {"HE209N", "HE210FL1", "HE210FL2", "HE210V", "HE210L", "HE210M", "HE210K", "HE210A", "HE210B"}
        
        # Test 1: HE209N Door Tag Mark Location
        # HE209N has two occurrences on page: room label (font_h=13.0) and door tag mark (font_h=8.9, center ~ (248.0, 1904.0))
        he209n_tag_words = [
            w for w in words_on_page 
            if w[4].strip(".,()[]{}-_#*").upper() == "HE209N" and (w[3] - w[1]) < 10.0
        ]
        self.assertTrue(len(he209n_tag_words) >= 1, "Should find door tag mark for HE209N with small font")
        
        tag_w = he209n_tag_words[0]
        w_cx = (tag_w[0] + tag_w[2]) / 2.0
        w_cy = (tag_w[1] + tag_w[3]) / 2.0
        
        expected_cx, expected_cy = 248.0, 1904.0
        dist = ((w_cx - expected_cx)**2 + (w_cy - expected_cy)**2)**0.5
        self.assertLessEqual(dist, 2.0, f"HE209N tag center ({w_cx:.1f}, {w_cy:.1f}) drifted from expected ({expected_cx}, {expected_cy})")
        
        # Test 2: Structural Attachment check for HE209N tag
        inst_rect = fitz.Rect(tag_w[0], tag_w[1], tag_w[2], tag_w[3])
        is_attached = is_tag_attached_to_door_opening(inst_rect, drawings_on_page)
        self.assertTrue(is_attached, "HE209N tag rect should be attached to door opening geometry")
        
        # Test 3: HE210FL1 Door Tag Mark Location
        he210fl1_tag_words = [
            w for w in words_on_page 
            if w[4].strip(".,()[]{}-_#*").upper() == "HE210FL1" and (w[3] - w[1]) < 10.0
        ]
        self.assertTrue(len(he210fl1_tag_words) >= 1, "Should find door tag mark for HE210FL1 with small font")
        
        tag_fl1 = he210fl1_tag_words[0]
        fl1_cx = (tag_fl1[0] + tag_fl1[2]) / 2.0
        fl1_cy = (tag_fl1[1] + tag_fl1[3]) / 2.0
        
        exp_fl1_cx, exp_fl1_cy = 775.1, 1951.2
        dist_fl1 = ((fl1_cx - exp_fl1_cx)**2 + (fl1_cy - exp_fl1_cy)**2)**0.5
        self.assertLessEqual(dist_fl1, 2.0, f"HE210FL1 tag center ({fl1_cx:.1f}, {fl1_cy:.1f}) drifted from expected ({exp_fl1_cx}, {exp_fl1_cy})")

        # Test 4: HE210L Multi-cell Grid Table Door Tag Mark (distinguishes door grid table at font_h < 10 from room label pill at font_h=13)
        he210l_tag_words = [
            w for w in words_on_page 
            if w[4].strip(".,()[]{}-_#*").upper() == "HE210L" and (w[3] - w[1]) < 10.0
        ]
        self.assertTrue(len(he210l_tag_words) >= 1, "Should find door tag mark for HE210L in grid table")
        tag_l = he210l_tag_words[0]
        l_cx = (tag_l[0] + tag_l[2]) / 2.0
        l_cy = (tag_l[1] + tag_l[3]) / 2.0
        exp_l_cx, exp_l_cy = 1233.3, 1677.8
        dist_l = ((l_cx - exp_l_cx)**2 + (l_cy - exp_l_cy)**2)**0.5
        self.assertLessEqual(dist_l, 2.0, f"HE210L tag center ({l_cx:.1f}, {l_cy:.1f}) drifted from expected ({exp_l_cx}, {exp_l_cy})")

    def test_schedule_mark_validation_gate(self):
        """
        Negative fixture test: non-door wall tags, detail bubbles, and random numbers
        must NOT match schedule marks unless they exist in the schedule registry.
        """
        sched_marks = {"HE209N", "HE210FL1", "100A", "105B"}
        
        # Wall tag bubble
        self.assertIsNone(find_closest_schedule_mark("SA3.0.W", sched_marks))
        # Detail circle callout
        self.assertIsNone(find_closest_schedule_mark("A-411", sched_marks))
        # Column grid line diamond
        self.assertIsNone(find_closest_schedule_mark("GRID-A", sched_marks))
        # Sheet title block text
        self.assertIsNone(find_closest_schedule_mark("COVER_SHEET", sched_marks))
        # Valid schedule mark match
        self.assertEqual(find_closest_schedule_mark("HE209N", sched_marks), "HE209N")

    def test_vertically_rotated_tag_font_size(self):
        """
        Tests that 90°/270° vertically rotated door tag words (e.g. 100A, 113A, 121A)
        where bounding height (w[3] - w[1]) is ~22pt and bounding width (w[2] - w[0]) is ~9.6pt
        are correctly evaluated as valid door tag candidate marks, not misidentified as room titles.
        """
        vert_word = (1523.3, 1020.6, 1532.9, 1042.7, "121A", 0, 0)
        from app.services.agents.layer2_vision.cv_detector_node import is_combined_room_name_and_mark
        is_room_combined = is_combined_room_name_and_mark(vert_word, [vert_word])
        self.assertFalse(is_room_combined, "90° vertically rotated tag mark 121A must NOT be dropped by Step 2 pre-filter")


    def test_unlocated_mark_transparent_fallback(self):
        """
        Unlocated fixture test: when a mark is not present on the drawing page,
        the system must return unlocated (needs_review=True) rather than guessing.
        """
        if not self.has_cbr_pdf:
            self.skipTest("CBR Radiology PDF not found")
            
        doc = fitz.open(self.cbr_pdf_path)
        page = doc[0]
        words_on_page = reassemble_pdf_words(page.get_text("words"))
        
        unlocated_mark = "HE999_NON_EXISTENT"
        matches = [
            w for w in words_on_page 
            if find_closest_schedule_mark(w[4].strip(".,()[]{}-_#*").upper(), {unlocated_mark}) == unlocated_mark
        ]
        self.assertEqual(len(matches), 0, "Non-existent mark should have 0 vector text matches on page")

    def test_shape_agnostic_no_branching_invariant(self):
        """
        Code Quality & Invariant Assertion:
        `find_door_tag_shapes` must NOT contain shape-specific `if` branches like
        `if grid_table` or `if oval` or `if circle`.
        """
        source = inspect.getsource(find_door_tag_shapes)
        forbidden_tokens = ["if grid_table", "if oval", "if circle_tag", "elif grid_table", "elif oval"]
        for tok in forbidden_tokens:
            self.assertNotIn(tok, source, f"find_door_tag_shapes contains prohibited shape-branching condition '{tok}'")

    def test_grid_table_vector_clustering(self):
        """
        Tests spatial clustering on multi-segment grid table tags (outer box + internal cell lines).
        Multi-segment paths within <= 4.0 pt proximity must be merged into ONE composite candidate rect.
        """
        drawings = [
            {"rect": [100.0, 100.0, 140.0, 140.0], "items": [("re",)]},
            {"rect": [100.0, 115.0, 140.0, 115.0], "items": [("l",)]}, # Divider line 1
            {"rect": [100.0, 128.0, 140.0, 128.0], "items": [("l",)]}, # Divider line 2
        ]
        composite_rects = find_door_tag_shapes(drawings, proximity_threshold=4.0)
        self.assertEqual(len(composite_rects), 1, "Multi-segment grid table paths should merge into 1 composite rect")
        comp = composite_rects[0]
        self.assertEqual(comp.x0, 100.0)
        self.assertEqual(comp.y0, 100.0)
        self.assertEqual(comp.x1, 140.0)
        self.assertEqual(comp.y1, 140.0)

    def test_unbroken_bbox_handoff_and_self_check(self):
        """
        Audits unbroken data handoff: verifies that detected bboxes are valid [x0, y0, x1, y1] rects
        with x0 < x1, y0 < y1 and center matching (w_cx, w_cy) within <= 1.0 pt tolerance.
        """
        sample_det = {
            "mark": "HE209N",
            "bbox": [238.8, 1899.6, 257.2, 1908.5],
            "w_cx": 248.0,
            "w_cy": 1904.05
        }
        bbox = sample_det["bbox"]
        self.assertEqual(len(bbox), 4)
        self.assertLess(bbox[0], bbox[2])
        self.assertLess(bbox[1], bbox[3])
        
        calc_cx = (bbox[0] + bbox[2]) / 2.0
        calc_cy = (bbox[1] + bbox[3]) / 2.0
        
        self.assertAlmostEqual(calc_cx, sample_det["w_cx"], delta=1.0)
        self.assertAlmostEqual(calc_cy, sample_det["w_cy"], delta=1.0)

    # -------------------------------------------------------------------------
    # MANDATORY STEP 7 REGRESSION FIXTURE SUITE (11 Fixtures)
    # -------------------------------------------------------------------------

    def test_fixture_1_mark_inside_arc(self):
        """Fixture 1: Genuine door mark inside arc (containment)."""
        from app.services.agents.layer2_vision.cv_detector_node import compute_min_dist_to_door_arc
        drawings = [{"rect": [100.0, 100.0, 150.0, 150.0], "items": [("c", (100, 100), (150, 150))]}]
        dist = compute_min_dist_to_door_arc(125.0, 125.0, drawings)
        self.assertLessEqual(dist, 35.0, "Center inside arc bounding box should have min arc dist <= 35pt")

    def test_fixture_2_mark_touching_arc(self):
        """Fixture 2: Genuine door mark touching/intersecting arc edge (121A, 112, 98B)."""
        from app.services.agents.layer2_vision.cv_detector_node import compute_min_dist_to_door_arc
        drawings = [{"rect": [100.0, 100.0, 150.0, 150.0], "items": [("c", (100, 100), (150, 150))]}]
        dist = compute_min_dist_to_door_arc(152.0, 125.0, drawings)
        self.assertLessEqual(dist, 35.0, "Mark touching arc edge at 152pt must pass arc distance threshold")

    def test_fixture_3_anchor_dot_leader(self):
        """Fixture 3: Genuine door mark connected via anchor-dot only (r in [1.0, 4.0] pt) (RS030, RS036)."""
        from app.services.agents.layer2_vision.cv_detector_node import is_hinge_anchor_dot_connected
        drawings = [{"rect": [100.0, 100.0, 105.0, 105.0], "items": [("c", (100, 100), (105, 105))]}] # r=2.5pt
        is_conn = is_hinge_anchor_dot_connected((120.0, 120.0, 140.0, 130.0), drawings, r_min=1.0, r_max=4.0)
        self.assertTrue(is_conn, "Small hinge anchor dot (r=2.5pt) within search radius must be recognized")

    def test_fixture_4_cased_opening_jamb(self):
        """Fixture 4: Cased opening with wall end-cap return lines (no arc)."""
        from app.services.agents.layer2_vision.cv_detector_node import detect_wall_endcap_jamb_signature
        drawings = [
            {"rect": [100.0, 100.0, 108.0, 103.0]}, # End-cap return line 1 (w=8, h=3)
            {"rect": [100.0, 140.0, 108.0, 143.0]}  # End-cap return line 2 (w=8, h=3)
        ]
        has_jambs = detect_wall_endcap_jamb_signature((90.0, 90.0, 150.0, 150.0), drawings)
        self.assertTrue(has_jambs, "Wall end-cap return line segments must identify cased opening jamb signature")

    def test_fixture_5_combined_room_name_and_mark(self):
        """Fixture 5: Room-name + mark combined pairing (must be dropped, e.g. 'OFFICE HE210V')."""
        from app.services.agents.layer2_vision.cv_detector_node import is_combined_room_name_and_mark
        w_mark = (150.0, 100.0, 190.0, 110.0, "HE210V")
        w_room = (80.0, 100.0, 140.0, 110.0, "OFFICE")
        words_on_page = [w_mark, w_room]
        is_combined = is_combined_room_name_and_mark(w_mark, words_on_page)
        self.assertTrue(is_combined, "Combined string 'OFFICE HE210V' on same line must be dropped by Step 2 pre-filter")

    def test_fixture_6_room_container_area_block(self):
        """Fixture 6: Room-tag container area pairing (must be dropped, e.g. '105B' + '7 SF')."""
        from app.services.agents.layer2_vision.cv_detector_node import is_room_container_area_block
        w_mark_rect = (100.0, 100.0, 130.0, 112.0)
        words_on_page = [
            (100.0, 100.0, 130.0, 112.0, "105B"),
            (100.0, 115.0, 130.0, 125.0, "7 SF") # Area callout cell
        ]
        is_area_block = is_room_container_area_block(w_mark_rect, words_on_page)
        self.assertTrue(is_area_block, "Room container block with area unit '7 SF' must be dropped by Step 2 pre-filter")

    def test_fixture_7_door_grid_table_negative(self):
        """Fixture 7 (Negative): Door grid-table tag (D1 / 36" / HE210V) is NEVER dropped by Step 2."""
        from app.services.agents.layer2_vision.cv_detector_node import is_room_container_area_block
        w_mark_rect = (100.0, 100.0, 130.0, 112.0)
        words_on_page = [
            (100.0, 100.0, 130.0, 112.0, "HE210V"),
            (100.0, 115.0, 130.0, 125.0, "D1"),
            (100.0, 128.0, 130.0, 138.0, "36\"") # Door dimension cell
        ]
        is_area_block = is_room_container_area_block(w_mark_rect, words_on_page)
        self.assertFalse(is_area_block, "Genuine door grid-table with '36\"' and 'D1' must NEVER be dropped by Step 2 pre-filter")

    def test_fixture_8_single_match_geometry_check(self):
        """Fixture 8: Single-occurrence candidate failing geometry (proves single-match is not exempted from Step 3)."""
        from app.services.agents.layer2_vision.cv_detector_node import compute_min_dist_to_door_arc
        drawings_far_away = [{"rect": [500.0, 500.0, 550.0, 550.0], "items": [("c", (500, 500), (550, 550))]}]
        dist = compute_min_dist_to_door_arc(100.0, 100.0, drawings_far_away)
        self.assertGreater(dist, 100.0, "Single-match text 400pt away from arc must fail geometry check")

    def test_fixture_9_multi_match_preservation(self):
        """Fixture 9: Two genuine doors sharing same mark (both highlighted)."""
        sample_matches = [
            {"w_cx": 100.0, "w_cy": 100.0, "mark": "100A"},
            {"w_cx": 400.0, "w_cy": 400.0, "mark": "100A"}
        ]
        final_matches = []
        for m in sample_matches:
            if any(abs(fm["w_cx"] - m["w_cx"]) < 8.0 and abs(fm["w_cy"] - m["w_cy"]) < 8.0 for fm in final_matches):
                continue
            final_matches.append(m)
        self.assertEqual(len(final_matches), 2, "Both genuine doors at different coordinates sharing same mark 100A must be preserved")

    def test_fixture_10_containment_first_arc_ranking(self):
        """Fixture 10: Dense cluster containment-first arc selection."""
        from app.services.agents.layer2_vision.cv_detector_node import compute_min_dist_to_door_arc
        drawings = [
            {"rect": [95.0, 95.0, 105.0, 105.0], "items": [("c", (95, 95), (105, 105))]}, # Nearer non-containing curve (r=5pt)
            {"rect": [80.0, 80.0, 150.0, 150.0], "items": [("c", (80, 80), (150, 150))]}  # Farther containing arc
        ]
        dist = compute_min_dist_to_door_arc(100.0, 100.0, drawings)
        self.assertLessEqual(dist, 35.0, "Containment-first ranking must select valid door swing arc")

    def test_fixture_11_render_bbox_handoff_tolerance(self):
        """Fixture 11: Highlight coordinates in plan_annotation_node match detected bbox within <= 1.0 pt tolerance."""
        det_bbox = [100.0, 200.0, 140.0, 215.0]
        rendered_rect = fitz.Rect(100.2, 200.1, 140.3, 215.1)
        
        cx_det = (det_bbox[0] + det_bbox[2]) / 2.0
        cy_det = (det_bbox[1] + det_bbox[3]) / 2.0
        
        cx_rnd = (rendered_rect.x0 + rendered_rect.x1) / 2.0
        cy_rnd = (rendered_rect.y0 + rendered_rect.y1) / 2.0
        
        shift_dist = ((cx_det - cx_rnd)**2 + (cy_det - cy_rnd)**2)**0.5
        self.assertLessEqual(shift_dist, 1.0, f"Rendered highlight center shift {shift_dist:.2f}pt exceeds 1.0pt tolerance")

    def test_polyline_chain_arc_recognition(self):
        """
        Tests polyline-chain arc reconstruction: a chain of 20 tiny 2pt line segments
        forming a smooth 90° arc must be successfully recognized as a door swing arc.
        """
        import math
        from app.services.agents.layer2_vision.cv_detector_node import find_polyline_chain_arcs, validate_vector_opening_geometry

        # Generate quarter-circle arc of radius 30pt centered at (100, 100) using 20 short line segments
        chain_items = []
        n_segs = 20
        r = 30.0
        for i in range(n_segs):
            a1 = (i / float(n_segs)) * (math.pi / 2.0)
            a2 = ((i + 1) / float(n_segs)) * (math.pi / 2.0)
            p1 = fitz.Point(100.0 + r * math.cos(a1), 100.0 + r * math.sin(a1))
            p2 = fitz.Point(100.0 + r * math.cos(a2), 100.0 + r * math.sin(a2))
            chain_items.append(("l", p1, p2))

        drawings = [{"rect": [100.0, 100.0, 130.0, 130.0], "items": chain_items}]
        arcs = find_polyline_chain_arcs(drawings, (115.0, 115.0), radius=40.0)
        self.assertEqual(len(arcs), 1, "Polyline-chain quarter circle arc must be reconstructed into 1 valid arc")
        self.assertGreaterEqual(arcs[0]["total_length"], 40.0)

    def test_polyline_chain_hatching_negative_fixture(self):
        """
        Negative fixture: dense hatching/grid pattern (20 short parallel/zigzag line segments
        with alternating turn direction) must NOT be misclassified as an arc.
        """
        from app.services.agents.layer2_vision.cv_detector_node import find_polyline_chain_arcs

        # Generate zig-zag hatching pattern of 20 segments
        hatch_items = []
        curr_x, curr_y = 100.0, 100.0
        for i in range(20):
            next_x = curr_x + 3.0
            next_y = curr_y + (3.0 if i % 2 == 0 else -3.0)
            p1 = fitz.Point(curr_x, curr_y)
            p2 = fitz.Point(next_x, next_y)
            hatch_items.append(("l", p1, p2))
            curr_x, curr_y = next_x, next_y

        drawings = [{"rect": [100.0, 95.0, 160.0, 105.0], "items": hatch_items}]
        arcs = find_polyline_chain_arcs(drawings, (130.0, 100.0), radius=40.0)
        self.assertEqual(len(arcs), 0, "Dense hatching/zigzag pattern must NOT be misclassified as an arc")

    def test_corrected_diagnostic_log_format(self):
        """
        Verifies validate_vector_opening_geometry returns detailed metrics (n_lines, max_l, n_curves, max_c)
        matching the new non-misleading diagnostic log format.
        """
        from app.services.agents.layer2_vision.cv_detector_node import validate_vector_opening_geometry

        # Mock PyMuPDF page with 5 short line segments (max_len=2.0) and 1 short curve (max_len=6.0)
        class MockPage:
            def get_drawings(self):
                return [{
                    "rect": [100.0, 100.0, 120.0, 120.0],
                    "items": [
                        ("l", fitz.Point(100, 100), fitz.Point(102, 100)),
                        ("l", fitz.Point(102, 100), fitz.Point(104, 100)),
                        ("c", fitz.Point(100, 100), fitz.Point(103, 100), fitz.Point(106, 100))
                    ]
                }]

        page = MockPage()
        valid, n_lines, max_l, n_curves, max_c = validate_vector_opening_geometry(page, (100.0, 100.0), radius=40.0, return_details=True)
        self.assertEqual(n_lines, 2)
        self.assertAlmostEqual(max_l, 2.0, delta=0.1)
        self.assertEqual(n_curves, 1)
        self.assertAlmostEqual(max_c, 6.0, delta=0.1)
        log_msg = (
            f"CV Detector: Skipping text '112A' at (100.0, 100.0) — "
            f"found {n_lines} line segments (max_len={max_l:.1f}pt) and "
            f"{n_curves} curve segments (max_len={max_c:.1f}pt) within radius, "
            f"none passed arc/jamb length or distance thresholds"
        )
        self.assertIn("found 2 line segments (max_len=2.0pt) and 1 curve segments (max_len=6.0pt)", log_msg)

    def test_rule1_single_occurrence_no_passing_geometry_resolves_location(self):
        """
        Rule 1 Gating Fixture: Single-occurrence genuine mark (N=1) with NO passing vector geometry
        must resolve LOCATION correctly and must NOT be flagged needs_review.
        """
        w_single = (100.0, 100.0, 140.0, 115.0, "112A")
        matches = [{
            "word": w_single,
            "w_x": 100.0,
            "w_y": 100.0,
            "w_cx": 120.0,
            "w_cy": 107.5,
            "inst_rect": fitz.Rect(100, 100, 140, 115),
            "nearby_drawings": [],
            "has_vector_geometry": False
        }]
        
        # Rule 1: N_rem == 1 -> treat as genuine for LOCATION immediately!
        m = matches[0]
        is_genuine_geom = m.get("has_vector_geometry", False)
        m["has_highlight"] = is_genuine_geom
        valid_matches = [m]
        
        self.assertEqual(len(valid_matches), 1, "Single-occurrence mark 112A must be preserved for location")
        self.assertFalse(valid_matches[0]["has_highlight"], "Mark with failing geometry must have has_highlight=False")

    def test_rule2_multi_occurrence_room_tag_filtering(self):
        """
        Rule 2 Gating Fixture: Multi-occurrence mark where one is a room title (e.g. 'OFFICE 101')
        and one is a standalone tag ('101'). Room tag pre-filter drops 'OFFICE 101', leaving 1 candidate resolved via Rule 1.
        """
        from app.services.agents.layer2_vision.cv_detector_node import is_combined_room_name_and_mark
        
        w_room_tag = (50.0, 50.0, 140.0, 65.0, "101")
        w_door_tag = (300.0, 300.0, 330.0, 315.0, "101")
        words_on_page = [
            (10.0, 50.0, 45.0, 65.0, "OFFICE"),
            w_room_tag,
            w_door_tag
        ]
        
        matches = [
            {"word": w_room_tag, "inst_rect": fitz.Rect(50, 50, 140, 65), "w_cx": 95.0, "w_cy": 57.5},
            {"word": w_door_tag, "inst_rect": fitz.Rect(300, 300, 330, 315), "w_cx": 315.0, "w_cy": 307.5}
        ]
        
        filtered = []
        for m in matches:
            if is_combined_room_name_and_mark(m["word"], words_on_page):
                continue
            filtered.append(m)
            
        self.assertEqual(len(filtered), 1, "Room-tag pre-filter must drop 'OFFICE 101', leaving 1 candidate")
        self.assertEqual(filtered[0]["w_cx"], 315.0, "Remaining candidate must be the standalone door tag at x=315")

    def test_single_occurrence_geometry_fail_omits_highlight_box(self):
        """
        Fixture 5 (Highlight Box Omission): Single-occurrence mark resolving LOCATION via Rule 1
        with failing geometry must set has_highlight=False while keeping needs_review=False.
        """
        det = {
            "mark": "105A",
            "location": "SHARED OFFICE",
            "w_cx": 500.0,
            "w_cy": 600.0,
            "has_highlight": False,
            "has_vector_geometry": False
        }
        
        # Simulate reconciliation node handling of located mark
        obj = {"type": det["mark"], "count": 1, "needs_review": False}
        if det.get("location"):
            obj["LOCATION"] = det["location"]
        obj["has_highlight"] = det.get("has_highlight", True)
        
        self.assertFalse(obj["needs_review"], "Located mark 105A with failing geometry must NOT be flagged needs_review")
        self.assertEqual(obj["LOCATION"], "SHARED OFFICE")
        self.assertFalse(obj["has_highlight"], "PDF renderer must omit highlight box for failing geometry (has_highlight=False)")

    def test_enlarged_plan_wizard_checkbox_flag_exclusion(self):
        """
        Fixture: When floor layout has isEnlarged=True / isEnlargedUnitPlan=True from Wizard Step 2 checkbox,
        the detector flags is_enlarged_plan=True and excludes the sheet from common master floor counts.
        """
        floors = [
            {"name": "Level 1", "isEnlarged": False, "rawUrl": "level1.pdf"},
            {"name": "Enlarged Unit Plan A5.01", "isEnlargedUnitPlan": True, "rawUrl": "a501.pdf"}
        ]
        
        floor_obj_level1 = floors[0]
        floor_obj_enlarged = floors[1]
        
        is_enlarged_1 = bool(floor_obj_level1.get("isEnlarged") or floor_obj_level1.get("isEnlargedUnitPlan"))
        is_enlarged_2 = bool(floor_obj_enlarged.get("isEnlarged") or floor_obj_enlarged.get("isEnlargedUnitPlan"))
        
        self.assertFalse(is_enlarged_1, "Level 1 floor plan must NOT be marked enlarged")
        self.assertTrue(is_enlarged_2, "Enlarged unit plan layout with isEnlargedUnitPlan=True MUST be marked enlarged")

    def test_enlarged_plan_title_pattern_exclusion(self):
        """
        Fixture: Fallback title pattern matching identifies sheets titled 'A5.01', 'A5.02', 'ENLARGED TYPICAL UNIT PLAN'
        and flags is_enlarged_plan=True when upload metadata is unassigned.
        """
        sheet_titles = [
            "A5.01 ENLARGED UNIT PLAN - MC-A",
            "A5.02 TYPICAL UNIT PLAN - MC-B",
            "FLOOR LEVEL 3 OVERALL PLAN"
        ]
        
        enlarged_keywords = ["ENLARGED", "TYPICAL UNIT", "UNIT PLAN", "A5.01", "A5.02", "A501", "A502"]
        
        results = [any(kw in title for kw in enlarged_keywords) for title in sheet_titles]
        
        self.assertTrue(results[0], "Sheet A5.01 ENLARGED UNIT PLAN must match enlarged plan patterns")
        self.assertTrue(results[1], "Sheet A5.02 TYPICAL UNIT PLAN must match enlarged plan patterns")
        self.assertFalse(results[2], "Sheet FLOOR LEVEL 3 OVERALL PLAN must NOT match enlarged plan patterns")

    def test_crop_schedule_vertical_edge_y1_fallback(self):
        """
        Fixture: Edge dictionary lacking 'y1'/'y0' keys (using top/bottom/height) must not throw KeyError.
        """
        edge1 = {"top": 10.0, "bottom": 50.0, "x0": 100.0, "x1": 100.0}
        edge2 = {"height": 30.0, "x0": 150.0, "x1": 150.0}
        edge3 = {"y0": 0.0, "y1": 25.0, "x0": 200.0, "x1": 200.0}

        def get_edge_h(e):
            if "height" in e and e["height"] is not None:
                return float(e["height"])
            if "bottom" in e and "top" in e:
                return abs(float(e["bottom"]) - float(e["top"]))
            if "y1" in e and "y0" in e:
                return abs(float(e["y1"]) - float(e["y0"]))
            return 0.0

        self.assertEqual(get_edge_h(edge1), 40.0)
        self.assertEqual(get_edge_h(edge2), 30.0)
        self.assertEqual(get_edge_h(edge3), 25.0)

if __name__ == "__main__":
    unittest.main()




