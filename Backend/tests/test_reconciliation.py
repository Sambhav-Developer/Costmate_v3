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

if __name__ == "__main__":
    unittest.main()
