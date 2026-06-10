"""
Unit tests for Phase 3 Computer Vision Inspector & RoboClaw Actuator.
"""

import os
import sys
import unittest
import shutil
import logging

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.actuator import RoboClawActuator
from src.vision_inspector import VisionInspector

class TestActuator(unittest.TestCase):
    def test_simulation_actuator(self):
        """Verify that RoboClawActuator runs correctly in simulation mode."""
        actuator = RoboClawActuator(simulation=True)
        self.assertTrue(actuator.simulation)
        self.assertTrue(actuator.trigger_alarm(True))
        self.assertTrue(actuator.trigger_reject())
        self.assertTrue(actuator.trigger_alarm(False))

class TestVisionInspector(unittest.TestCase):
    def setUp(self):
        # Create directories for testing
        os.makedirs("data/test_inputs", exist_ok=True)
        os.makedirs("data/defects", exist_ok=True)
        
        # Setup dummy test files
        self.ok_image_path = "data/test_inputs/item_ok_001.jpg"
        self.defect_image_path = "data/test_inputs/item_defect_002.jpg"
        
        for path in [self.ok_image_path, self.defect_image_path]:
            with open(path, "wb") as f:
                f.write(b"mock image content")
                
        # Redirect logger output to avoid cluttered console during tests
        logging.getLogger("vision").setLevel(logging.ERROR)
        logging.getLogger("actuator").setLevel(logging.ERROR)

    def tearDown(self):
        # Clean up temporary test files
        shutil.rmtree("data/test_inputs", ignore_errors=True)
        
        # Clean up files created in data/defects during execution
        if os.path.exists("data/defects"):
            for file in os.listdir("data/defects"):
                os.remove(os.path.join("data/defects", file))

    def test_simulation_inspection_pass(self):
        """Verify that compliant product images pass the inspection without triggering defects."""
        actuator = RoboClawActuator(simulation=True)
        inspector = VisionInspector(simulation=True, actuator=actuator)
        
        result = inspector.inspect_image(self.ok_image_path)
        self.assertFalse(result["has_defect"])
        self.assertEqual(len(result["detections"]), 0)

    def test_simulation_inspection_fail(self):
        """Verify that defective images trigger the rejection alarm and copy the image to target folder."""
        actuator = RoboClawActuator(simulation=True)
        inspector = VisionInspector(simulation=True, actuator=actuator)
        
        result = inspector.inspect_image(self.defect_image_path)
        self.assertTrue(result["has_defect"])
        self.assertGreater(len(result["detections"]), 0)
        self.assertEqual(result["detections"][0]["label"], "defect")
        self.assertGreaterEqual(result["detections"][0]["confidence"], 0.80)
        
        # Check if defect file was copied
        defect_files = os.listdir("data/defects")
        self.assertGreater(len(defect_files), 0, "Defect image should be copied to data/defects")
        self.assertTrue(any("defect_" in f for f in defect_files))

if __name__ == "__main__":
    unittest.main()
