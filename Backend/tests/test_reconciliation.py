import sys
import os
import unittest
import asyncio

# Add Backend folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agents.layer3_human.reconciliation_node import reconciliation_node

class TestReconciliation(unittest.TestCase):
    def test_double_acting_detection(self):
        # 1. Test case: Comment contains "DBL ACT"
        state_dbl_act = {
            "schedule_data": [
                {
                    "mark": "300-03",
                    "comments": "DBL ACT",
                    "door type": "WOOD",
                    "material": "WD"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "300-03",
                        "bbox": [100, 100, 150, 120],
                        "w_cx": 125,
                        "w_cy": 110,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "DA",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_dbl_act))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "DA")
        
        # 2. Test case: Comment contains "ANTI-BARRICADE"
        state_anti_barricade = {
            "schedule_data": [
                {
                    "mark": "300-35",
                    "comments": "ANTI-BARRICADE DOOR",
                    "door type": "METAL",
                    "material": "HM"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "300-35",
                        "bbox": [200, 200, 250, 220],
                        "w_cx": 225,
                        "w_cy": 210,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "DA",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        
        res = loop.run_until_complete(reconciliation_node(state_anti_barricade))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "DA")

        # 3. Test case: Comment contains "DOUBLE ACTING"
        state_double_acting = {
            "schedule_data": [
                {
                    "mark": "F108",
                    "comments": "DOUBLE ACTING DOOR",
                    "door type": "METAL",
                    "material": "HM"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "F108",
                        "bbox": [300, 300, 350, 320],
                        "w_cx": 325,
                        "w_cy": 310,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "DA",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        
        res = loop.run_until_complete(reconciliation_node(state_double_acting))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "DA")

    def test_barn_door_detection(self):
        state_barn = {
            "schedule_data": [
                {
                    "mark": "B101",
                    "comments": "BARN DOOR WITH SURFACE SLIDING HARDWARE",
                    "door type": "BARN",
                    "material": "WD"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "B101",
                        "bbox": [100, 100, 150, 120],
                        "w_cx": 125,
                        "w_cy": 110,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "SLD",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_barn))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "SLD")

    def test_double_acting_regression(self):
        # Test case: Unrelated comments like "AUTOMATIC, CR" should NOT trigger DA
        state_normal = {
            "schedule_data": [
                {
                    "mark": "300-04",
                    "comments": "AUTOMATIC, CR",
                    "door type": "WOOD",
                    "material": "WD"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "300-04",
                        "bbox": [400, 400, 450, 420],
                        "w_cx": 425,
                        "w_cy": 410,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "SGL",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_normal))
        doors = res["qa_prefilled"]["doors"]
        self.assertNotEqual(doors[0]["_reconciled_opening_mode"], "DA")

    def test_storefront_classification(self):
        # 1. Storefront case: Door material is N/A, frame is N/A
        state_storefront = {
            "schedule_data": [
                {
                    "mark": "98C",
                    "door type": "CO",
                    "door material": "N/A",
                    "frame material": "",
                    "comments": "STOREFRONT UNIT"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "98C",
                        "bbox": [500, 500, 550, 520],
                        "w_cx": 525,
                        "w_cy": 510,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "CO",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_storefront))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "STOREFRONT")

        # 2. Cased Opening regression case: Door material N/A but frame is wood/HM (legit CO, not storefront)
        state_cased = {
            "schedule_data": [
                {
                    "mark": "100A",
                    "door type": "CO",
                    "door material": "N/A",
                    "frame material": "WD",
                    "comments": "CASED OPENING"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "100A",
                        "bbox": [600, 600, 650, 620],
                        "w_cx": 625,
                        "w_cy": 610,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "CO",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        res = loop.run_until_complete(reconciliation_node(state_cased))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "CO")

        # 3. Storefront case: Door type is CO, materials blank/NA, comments empty, but has Hardware Set (indicates storefront pivots/closures)
        state_storefront_hw = {
            "schedule_data": [
                {
                    "mark": "98C",
                    "door type": "CO",
                    "door material": "N/A",
                    "frame material": "",
                    "hardware group no": "SET 8",
                    "comments": ""
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "98C",
                        "bbox": [500, 500, 550, 520],
                        "w_cx": 525,
                        "w_cy": 510,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "CO",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        res = loop.run_until_complete(reconciliation_node(state_storefront_hw))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "STOREFRONT")

        # 4. Cased opening case: Door type CO, materials blank/NA, comments empty, NO hardware set (remains CO)
        state_cased_no_hw = {
            "schedule_data": [
                {
                    "mark": "3.0 - THIRD",
                    "door type": "CO",
                    "door material": "N/A",
                    "frame material": "",
                    "hardware group no": "",
                    "comments": ""
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "3.0 - THIRD",
                        "bbox": [500, 500, 550, 520],
                        "w_cx": 525,
                        "w_cy": 510,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "CO",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        res = loop.run_until_complete(reconciliation_node(state_cased_no_hw))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "CO")

        # 5. Wood door in Aluminum Frame case: WD/GL door material with ALUM frame material (In Scope Wood Door, NOT Storefront)
        state_wd_alum = {
            "schedule_data": [
                {
                    "mark": "200",
                    "door type": "FG",
                    "door material": "WD/GL",
                    "frame material": "ALUM",
                    "comments": ""
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "200",
                        "bbox": [500, 500, 550, 520],
                        "w_cx": 525,
                        "w_cy": 510,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "SGL",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        res = loop.run_until_complete(reconciliation_node(state_wd_alum))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "SGL")
        self.assertEqual(doors[0]["_reconciled_int_ext"], "Interior")

        # 6. Panel A fallback case: AL-FG panel material without WD/HM (Storefront)
        state_panel_alfg = {
            "schedule_data": [
                {
                    "mark": "301",
                    "panel a": "AL-FG",
                    "comments": ""
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "301",
                        "bbox": [500, 500, 550, 520],
                        "w_cx": 525,
                        "w_cy": 510,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "SGL",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        res = loop.run_until_complete(reconciliation_node(state_panel_alfg))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "STOREFRONT")

        # 7. One present AL material and frame material dash '-' (Storefront)
        state_al_dash = {
            "schedule_data": [
                {
                    "mark": "302",
                    "door material": "AL",
                    "frame material": "-",
                    "comments": ""
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "302",
                        "bbox": [500, 500, 550, 520],
                        "w_cx": 525,
                        "w_cy": 510,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "SGL",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        res = loop.run_until_complete(reconciliation_node(state_al_dash))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "STOREFRONT")

    def test_prep_door_frame_regression(self):
        # Relocated door with "PREP DOOR/FRAME" in comments should NOT trigger PR (remains SGL)
        state_relocated = {
            "schedule_data": [
                {
                    "mark": "99A",
                    "door width": "3'-0\"",
                    "frame type": "EX",
                    "door material": "SCWD",
                    "comments": "RELOCATE EXISTING DOOR - PREP DOOR/FRAME AS REQUIRED"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "99A",
                        "bbox": [700, 700, 750, 720],
                        "w_cx": 725,
                        "w_cy": 710,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "SGL",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_relocated))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["_reconciled_opening_mode"], "SGL")

    def test_deduplicate_same_mark_same_room(self):
        # Multiple crop detections scanning the same door callout bubble (e.g. HE210L) in the same room location
        state_duplicates = {
            "schedule_data": [
                {
                    "mark": "HE210L",
                    "location": "CONFERENCE ROOM",
                    "door material": "WD/GLASS",
                    "frame material": "HM",
                    "comments": "WOOD DOOR WITH VISION LITE"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "HE210L",
                        "location": "CONFERENCE ROOM",
                        "page_no": "0",
                        "w_cx": 100.0,
                        "w_cy": 100.0,
                        "floor_no": "1"
                    },
                    {
                        "mark": "HE210L",
                        "location": "CONFERENCE ROOM",
                        "page_no": "0",
                        "w_cx": 115.0,
                        "w_cy": 110.0,
                        "floor_no": "1"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_duplicates))
        doors = res["qa_prefilled"]["doors"]
        audit = res["reconciliation_audit"]
        
        # Count should be reconciled down to 1
        self.assertEqual(doors[0]["count"], 1)
        self.assertEqual(len(audit["deduplicated_rows"]), 1)
        self.assertEqual(audit["deduplicated_rows"][0]["mark"], "HE210L")

    def test_deep_interior_geometry_priority(self):
        # Step 5 Test: Door deep inside footprint (dist_to_boundary > 85pt) must classify Interior even if VLM guesses EXT
        state_deep_interior = {
            "schedule_data": [
                {
                    "mark": "HE210V",
                    "location": "OFFICE 101",
                    "door material": "WD",
                    "frame material": "HM"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "HE210V",
                        "location": "OFFICE 101",
                        "dist_to_boundary": 150.0,  # Deep inside footprint
                        "vlm_wall_type": "EXT",     # VLM guessed EXT based on double line
                        "int_ext": "Interior",
                        "w_cx": 500,
                        "w_cy": 500,
                        "floor_no": "1"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_deep_interior))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["INT/EXT"], "Interior")

    def test_perimeter_zone_vlm_tiebreaker(self):
        # Step 5 Test: Perimeter door (dist_to_boundary <= 85pt) with VLM EXT and no interior room name -> Exterior
        state_perimeter_ext = {
            "schedule_data": [
                {
                    "mark": "EXT-01",
                    "location": "MAIN ENTRY",
                    "door material": "AL",
                    "frame material": "AL"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "EXT-01",
                        "location": "MAIN ENTRY",
                        "dist_to_boundary": 30.0,   # Perimeter zone
                        "vlm_wall_type": "EXT",
                        "int_ext": "Exterior",
                        "w_cx": 50,
                        "w_cy": 50,
                        "floor_no": "1"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_perimeter_ext))
        doors = res["qa_prefilled"]["doors"]
        # Aluminum storefront entry -> Not in Scope or Exterior
        self.assertIn(doors[0]["INT/EXT"], ["Exterior", "Not in Scope"])

    def test_missing_location_geometry_fallback(self):
        # Step 5 Test: LOCATION fails to resolve upstream (Unknown), deep geometry distance -> Interior
        state_missing_loc = {
            "schedule_data": [
                {
                    "mark": "HE210L",
                    "location": "",
                    "door material": "WD",
                    "frame material": "HM"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "HE210L",
                        "location": "Unknown",
                        "dist_to_boundary": 200.0,
                        "vlm_wall_type": "EXT",
                        "int_ext": "Interior",
                        "w_cx": 600,
                        "w_cy": 600,
                        "floor_no": "1"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_missing_loc))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["INT/EXT"], "Interior")

    def test_schedule_location_and_floor_priority(self):
        # 1. Schedule contains explicit Room Name & Floor -> Must preserve Schedule values
        state_explicit = {
            "schedule_data": [
                {
                    "mark": "401A",
                    "room name": "CONF ROOM 305",
                    "floor": "3rd Floor",
                    "door material": "WD",
                    "frame material": "HM"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "401A",
                        "location": "HALLWAY OVERRIDE",
                        "floor_no": "1",
                        "w_cx": 100,
                        "w_cy": 100
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(reconciliation_node(state_explicit))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["LOCATION"], "CONF ROOM 305")
        self.assertEqual(doors[0]["FLOOR / LEVEL"], "3rd Floor")
        self.assertEqual(doors[0]["floor_no"], "3rd Floor")

        # 2. Schedule location is empty -> Fallback to CV spatial location detection
        state_fallback = {
            "schedule_data": [
                {
                    "mark": "401B",
                    "room name": "",
                    "floor": "",
                    "door material": "WD",
                    "frame material": "HM"
                }
            ],
            "cv_results": {
                "detections": [
                    {
                        "mark": "401B",
                        "location": "LOBBY 100",
                        "floor_no": "Level 1",
                        "w_cx": 200,
                        "w_cy": 200
                    }
                ]
            }
        }
        res = loop.run_until_complete(reconciliation_node(state_fallback))
        doors = res["qa_prefilled"]["doors"]
        self.assertEqual(doors[0]["LOCATION"], "LOBBY 100")
        self.assertEqual(doors[0]["FLOOR / LEVEL"], "Level 1")

    def test_sidelight_transom_clerestory_engine(self):
        from app.services.agents.layer2_vision.cv_detector_node import (
            scan_header_evidence,
            determine_schedule_convention,
            parse_frame_features_from_title,
            extract_convention_b_features
        )

        # 1. Test tokenized header scanner
        headers_with_shortcodes = ["MARK", "DOOR TYPE", "SL", "TR", "CL"]
        ev1 = scan_header_evidence(headers_with_shortcodes)
        self.assertTrue(ev1["has_sidelite_header"])
        self.assertTrue(ev1["has_transom_header"])
        self.assertTrue(ev1["has_clerestory_header"])
        self.assertTrue(ev1["has_any_evidence"])

        # Boundary check: "Track" shouldn't trigger "tr", "Class" shouldn't trigger "cl"
        headers_boundary = ["MARK", "TRACK TYPE", "CLASS CODE"]
        ev2 = scan_header_evidence(headers_boundary)
        self.assertFalse(ev2["has_any_evidence"])

        # Descriptive keywords check
        headers_desc = ["DOOR MARK", "SIDELITE WIDTH", "TRANSOM HEIGHT", "CLERESTORY"]
        ev3 = scan_header_evidence(headers_desc)
        self.assertTrue(ev3["has_sidelite_header"])
        self.assertTrue(ev3["has_transom_header"])
        self.assertTrue(ev3["has_clerestory_header"])

        # 2. Test convention determination priority hierarchy
        # Priority 1: Naming pattern heuristic (HM-002 baseline)
        sched_a = [
            {"frame_type": "HM-002", "sidelight width": "2'-0\"", "transom height": "1'-0\""},
            {"frame_type": "HM-012", "sidelight width": "2'-0\"", "transom height": "1'-0\""},
            {"frame_type": "HM-112", "sidelight width": "2'-0\"", "transom height": "1'-0\""}
        ]
        conv_a = determine_schedule_convention(sched_a, ["FRAME TYPE", "SIDELIGHT WIDTH", "TRANSOM HEIGHT"])
        self.assertEqual(conv_a, "CONVENTION_A")

        # Convention B: Baseline code has blank dimension values
        sched_b = [
            {"frame_type": "HM-002", "sidelight width": "-", "transom height": "-"},
            {"frame_type": "HM-012", "sidelight width": "2'-0\"", "transom height": "-"},
        ]
        conv_b = determine_schedule_convention(sched_b, ["FRAME TYPE", "SIDELIGHT WIDTH", "TRANSOM HEIGHT"])
        self.assertEqual(conv_b, "CONVENTION_B")

        # 3. Test Title Parser
        title1 = "HOLLOW METAL FRAME 2\" HEAD WITH (1) SIDELIGHT"
        f1 = parse_frame_features_from_title(title1)
        self.assertTrue(f1["has_sidelite"])
        self.assertFalse(f1["has_transom"])
        self.assertFalse(f1["has_clerestory"])

        title2 = "HOLLOW METAL FRAME WITH TRANSOM AND (1) SIDELIGHT"
        f2 = parse_frame_features_from_title(title2)
        self.assertTrue(f2["has_sidelite"])
        self.assertTrue(f2["has_transom"])
        self.assertFalse(f2["has_clerestory"])

        title3 = "STOREFRONT ASSEMBLY WITH CLERESTORY PANEL"
        f3 = parse_frame_features_from_title(title3)
        self.assertFalse(f3["has_sidelite"])
        self.assertFalse(f3["has_transom"])
        self.assertTrue(f3["has_clerestory"])

        # 4. Test Convention B Extract Features & Normalized Blank Filter
        row_b = {
            "sidelight qty": "1",
            "sidelight width": "1'-0\"",
            "transom height": " n/a ",
            "clerestory": "-"
        }
        fb = extract_convention_b_features(row_b)
        self.assertTrue(fb["has_sidelite"])
        self.assertFalse(fb["has_transom"])
        self.assertFalse(fb["has_clerestory"])

        # 5. Integration test: Reconciliation Node preserves door category & formats Estimator Note
        state_sidelite_door = {
            "schedule_data": [
                {
                    "mark": "D326",
                    "frame_type": "HM-012",
                    "door material": "WD",
                    "frame material": "HM",
                    "sidelight width": "2'-0\"",
                    "transom height": "1'-6\""
                }
            ],
            "elevation_sheet_map": {
                "HM-012": {"has_sidelite": True, "has_transom": True, "has_clerestory": False}
            },
            "cv_results": {
                "detections": [
                    {
                        "mark": "D326",
                        "bbox": [100, 100, 150, 150],
                        "w_cx": 125,
                        "w_cy": 125,
                        "floor_no": "1",
                        "int_ext": "Interior",
                        "vlm_opening_mode": "SGL",
                        "vlm_wall_type": "INT"
                    }
                ]
            }
        }
        loop = asyncio.get_event_loop()
        res_door = loop.run_until_complete(reconciliation_node(state_sidelite_door))
        doors = res_door["qa_prefilled"]["doors"]
        self.assertEqual(len(doors), 1) # Retains door takeoff category, not reclassified to window!
        self.assertTrue(doors[0]["has_sidelite"])
        self.assertTrue(doors[0]["has_transom"])
        self.assertFalse(doors[0]["has_clerestory"])
        self.assertEqual(doors[0]["estimator_note"], "Sidelight & Transom")
        self.assertTrue(doors[0]["orange_highlight"])
        self.assertEqual(doors[0]["highlight_color"], "#FFC000")


if __name__ == "__main__":
    unittest.main()

