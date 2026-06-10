"""
Unit and integration tests for RPA crawler & validator (Phase 1).
Launches the mock portal server and verifies the crawler and validator behavior.
"""

import os

# Set testing environment variables BEFORE importing modules
os.environ["PORTAL_URL"] = "http://localhost:8889"
os.environ["CRAWLER_USERNAME"] = "admin"
os.environ["CRAWLER_PASSWORD"] = "admin123"

import json
import unittest
import subprocess
import time
import socket
import asyncio
from dotenv import load_dotenv

# Import modules under test
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.validator import validate_raw_orders, OrderItem
from src.crawler import run_crawler

def is_port_in_use(port: int) -> bool:
    """Helper to check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

class TestValidator(unittest.TestCase):
    """Unit tests for validator.py schema enforcement."""

    def test_valid_order(self):
        """Test with correct order data."""
        valid_data = [
            {
                "order_id": "ORD-001",
                "vendor": "Supplier A",
                "order_date": "2026-05-25",
                "total_amount": 1500.75,
                "barcodes": ["8935001718224", "9780201379624"]
            }
        ]
        validated = validate_raw_orders(valid_data)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["order_id"], "ORD-001")
        self.assertEqual(validated[0]["total_amount"], 1500.75)

    def test_invalid_order_date(self):
        """Test with invalid date formats (should be rejected)."""
        invalid_data = [
            {
                "order_id": "ORD-002",
                "vendor": "Supplier B",
                "order_date": "25-05-2026", # Invalid format (DD-MM-YYYY)
                "total_amount": 100.0,
                "barcodes": ["12345"]
            }
        ]
        validated = validate_raw_orders(invalid_data)
        self.assertEqual(len(validated), 0) # Should be filtered out

    def test_negative_total_amount(self):
        """Test with negative total amount (should be rejected)."""
        invalid_data = [
            {
                "order_id": "ORD-003",
                "vendor": "Supplier C",
                "order_date": "2026-05-25",
                "total_amount": -50.0, # Must be greater than 0
                "barcodes": ["12345"]
            }
        ]
        validated = validate_raw_orders(invalid_data)
        self.assertEqual(len(validated), 0)

    def test_invalid_barcodes(self):
        """Test with non-alphanumeric barcodes (should be rejected)."""
        invalid_data = [
            {
                "order_id": "ORD-004",
                "vendor": "Supplier D",
                "order_date": "2026-05-25",
                "total_amount": 100.0,
                "barcodes": ["123-456"] # Contains hyphen (not alphanumeric)
            }
        ]
        validated = validate_raw_orders(invalid_data)
        self.assertEqual(len(validated), 0)


class TestCrawlerIntegration(unittest.TestCase):
    """Integration tests executing crawler.py against mock_server.py."""
    
    mock_server_proc = None

    @classmethod
    def setUpClass(cls):
        """Start mock server subprocess on port 8889."""
        print("\nStarting Mock Server for integration tests on port 8889...")
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "src", 
            "mock_server.py"
        )
        cls.mock_server_proc = subprocess.Popen(
            [sys.executable, server_path, "8889"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait up to 5 seconds for the server to spin up
        for _ in range(10):
            if is_port_in_use(8889):
                print("Mock Server is up and listening.")
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Mock Server failed to start on port 8889.")

    @classmethod
    def tearDownClass(cls):
        """Kill mock server subprocess."""
        if cls.mock_server_proc:
            print("\nShutting down Mock Server...")
            cls.mock_server_proc.terminate()
            cls.mock_server_proc.wait()
            print("Mock Server stopped.")

    def setUp(self):
        """Clean up generated files before each test."""
        for path in ["data/session.json", "data/raw_orders.json"]:
            if os.path.exists(path):
                os.remove(path)

    def test_crawler_e2e_run(self):
        """Test crawler.py running against the mock portal."""
        # Execute the crawler main function
        print("Running crawler against mock portal...")
        asyncio.run(run_crawler())
        
        # Verify output files
        self.assertTrue(os.path.exists("data/session.json"), "session.json should be created")
        self.assertTrue(os.path.exists("data/raw_orders.json"), "raw_orders.json should be created")
        
        # Validate content of raw_orders.json
        with open("data/raw_orders.json", "r", encoding="utf-8") as f:
            orders = json.load(f)
            
        self.assertGreater(len(orders), 0, "Should have successfully crawled and validated some orders")
        
        # Check specific orders from mock server database
        order_ids = [order["order_id"] for order in orders]
        # ORD-2026-001 (Valid) & ORD-2026-002 (Valid) must exist
        self.assertIn("ORD-2026-001", order_ids)
        self.assertIn("ORD-2026-002", order_ids)
        
        # ORD-2026-003 (Invalid date) & ORD-2026-004 (Negative amount) must be excluded
        self.assertNotIn("ORD-2026-003", order_ids)
        self.assertNotIn("ORD-2026-004", order_ids)
        
        print("Integration test passed successfully!")

if __name__ == "__main__":
    unittest.main()
