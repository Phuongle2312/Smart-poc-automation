"""
Unit and integration tests for Phase 2 RAG Analyzer.
Tests markdown chunking, local Qdrant indexing, and compliance logic verification.
"""

import os
import json
import unittest
import shutil
from typing import List

# Import modules under test
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.embed_knowledge import chunk_markdown_file, get_mock_embedding, build_vector_db, QDRANT_PATH, COLLECTION_NAME
from src.analyzer import run_analysis, REPORT_JSON_FILE, REPORT_TXT_FILE

RAW_ORDERS_TEST_FILE = "data/raw_orders.json"

class TestRAGInitialization(unittest.TestCase):
    """Tests the parsing, chunking, and mock embedding functionality."""

    def test_markdown_chunking(self):
        """Test parsing of knowledge.md into markdown section chunks."""
        chunks = chunk_markdown_file("rag/knowledge.md")
        # knowledge.md has exactly 3 level-2 headers (##)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0]["title"], "1. Quy định về Thời gian Giao hàng (SLA Delivery Timeline)")
        self.assertEqual(chunks[1]["title"], "2. Quy định về Mã vạch Sản phẩm (Product Barcode Regulations)")
        self.assertEqual(chunks[2]["title"], "3. Hạn mức Tài chính Đơn hàng (Order Financial Limits)")

    def test_mock_embedding_consistency(self):
        """Verify that identical text produces identical embedding vectors."""
        text = "Order compliance regulation"
        emb1 = get_mock_embedding(text)
        emb2 = get_mock_embedding(text)
        self.assertEqual(emb1, emb2)
        self.assertEqual(len(emb1), 768)

    def test_mock_embedding_distinction(self):
        """Verify that different texts produce different embedding vectors."""
        emb1 = get_mock_embedding("Rule number 1")
        emb2 = get_mock_embedding("Rule number 2")
        self.assertNotEqual(emb1, emb2)


class TestQdrantLocalAndAnalyzer(unittest.TestCase):
    """Integration test verifying local Qdrant upsert and compliance parsing."""

    def setUp(self):
        """Prepare raw orders mock data for analysis testing."""
        os.makedirs("data", exist_ok=True)
        
        from datetime import datetime, timedelta
        today_str = datetime.now().strftime("%Y-%m-%d")
        six_days_ago_str = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        
        # We will write a test raw_orders.json with predictable violations
        test_orders = [
            {
                "order_id": "TEST-001",
                "vendor": "Vina Supply Corp",
                "order_date": today_str,
                "total_amount": 15000.00, # Violates limit of 10,000 USD
                "barcodes": ["893123456789"]
            },
            {
                "order_id": "TEST-002",
                "vendor": "Global Tech Solutions",
                "order_date": today_str, # Delivered in 0 day (OK)
                "total_amount": 2500.00,
                "barcodes": ["123456789"] # Violates barcode prefix (must be 978 or 893)
            },
            {
                "order_id": "TEST-003",
                "vendor": "Sino Logistics", # Foreign vendor (5 days max)
                "order_date": six_days_ago_str, # Delivered in 6 days (Violates SLA: 6 > 5)
                "total_amount": 3500.00,
                "barcodes": ["8935001718224"]
            },
            {
                "order_id": "TEST-004",
                "vendor": "Domestic Supplier A", # Domestic vendor (2 days max)
                "order_date": today_str, # Delivered in 0 day (OK)
                "total_amount": 4000.00,
                "barcodes": ["8935001718225"] # (OK)
            }
        ]
        
        with open(RAW_ORDERS_TEST_FILE, "w", encoding="utf-8") as f:
            json.dump(test_orders, f)

    def tearDown(self):
        """Clean up generated reports after test runs."""
        for path in [REPORT_JSON_FILE, REPORT_TXT_FILE]:
            if os.path.exists(path):
                os.remove(path)

    def test_end_to_end_rag_analysis(self):
        """Execute Qdrant local embedding build and compliance run."""
        # 1. Build local database
        print("Indexing knowledge.md to Qdrant Local...")
        build_vector_db()
        self.assertTrue(os.path.exists(QDRANT_PATH), "Qdrant local directory should exist")
        
        # 2. Run analysis
        print("Running RAG compliance analyzer...")
        run_analysis()
        
        # 3. Verify reports
        self.assertTrue(os.path.exists(REPORT_JSON_FILE))
        self.assertTrue(os.path.exists(REPORT_TXT_FILE))
        
        with open(REPORT_JSON_FILE, "r", encoding="utf-8") as f:
            report_data = json.load(f)
            
        self.assertEqual(len(report_data), 4)
        
        # Extract analysis results by Order ID
        results_by_id = {order["order_id"]: order["analysis"] for order in report_data}
        
        # TEST-001: Violated Financial Limits (Vina Supply Corp > 10,000 USD)
        self.assertTrue(results_by_id["TEST-001"]["has_violation"])
        self.assertEqual(results_by_id["TEST-001"]["rule_violated"], "Order Financial Limits")
        
        # TEST-002: Violated Barcode Regulations (Global Tech Solutions barcode not 978/893)
        self.assertTrue(results_by_id["TEST-002"]["has_violation"])
        self.assertEqual(results_by_id["TEST-002"]["rule_violated"], "Product Barcode Regulations")
        
        # TEST-003: Violated SLA timeline (Sino Logistics delay 7 days > 5 days allowed)
        self.assertTrue(results_by_id["TEST-003"]["has_violation"])
        self.assertEqual(results_by_id["TEST-003"]["rule_violated"], "SLA Delivery Timeline")
        
        # TEST-004: Compliant
        self.assertFalse(results_by_id["TEST-004"]["has_violation"])
        self.assertIsNone(results_by_id["TEST-004"]["rule_violated"])
        
        print("RAG compliance test completed successfully!")

if __name__ == "__main__":
    unittest.main()
