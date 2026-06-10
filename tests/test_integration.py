"""
Integration tests for the entire PoC automation pipeline (Phase 1-4 E2E).
Launches the mock portal server, executes the orchestrator pipeline,
verifies outcomes, memory updates, and validates the self-healing capability.
"""

import os
import sys
import json
import time
import socket
import shutil
import unittest
import asyncio
import subprocess
from dotenv import load_dotenv

# Ensure project root in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.agent_orchestrator import HermesOrchestrator, MEMORY_FILE, STATE_FILE, SELECTORS_FILE
from src.embed_knowledge import build_vector_db

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

class TestE2EPipeline(unittest.TestCase):
    mock_server_proc = None

    @classmethod
    def setUpClass(cls):
        """Start mock server on port 8890 for integration testing."""
        os.environ["PORTAL_URL"] = "http://localhost:8890"
        os.environ["CRAWLER_USERNAME"] = "admin"
        os.environ["CRAWLER_PASSWORD"] = "admin123"
        os.environ["ROBOCLAW_SIMULATION"] = "true"
        os.environ["VISION_SIMULATION"] = "true"
        
        # Build Vector DB before running tests
        print("Preparing Vector DB...")
        build_vector_db()

        print("Starting Mock Server on port 8890...")
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src",
            "mock_server.py"
        )
        cls.mock_server_proc = subprocess.Popen(
            [sys.executable, server_path, "8890"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server
        for _ in range(10):
            if is_port_in_use(8890):
                print("Mock Server is listening.")
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Mock Server failed to start on port 8890.")

    @classmethod
    def tearDownClass(cls):
        """Shutdown mock server."""
        if cls.mock_server_proc:
            print("Terminating Mock Server...")
            cls.mock_server_proc.terminate()
            cls.mock_server_proc.wait()
            print("Mock Server stopped.")

    def setUp(self):
        # Reset files
        for path in ["data/session.json", "data/raw_orders.json", "data/report.json", "data/report.txt", SELECTORS_FILE]:
            if os.path.exists(path):
                os.remove(path)
        
        # Reset memory files
        for path in [MEMORY_FILE, STATE_FILE]:
            if os.path.exists(path):
                os.remove(path)

    def tearDown(self):
        # Cleanup test defects directory
        if os.path.exists("data/defects"):
            shutil.rmtree("data/defects", ignore_errors=True)

    def test_pipeline_normal_run(self):
        """Verify the full pipeline runs successfully from E2E under normal conditions."""
        orchestrator = HermesOrchestrator(simulation=True)
        
        # Execute run
        stats = asyncio.run(orchestrator.run_pipeline())
        
        # Verify stages status
        self.assertEqual(stats["crawler"], "success")
        self.assertEqual(stats["analyzer"], "success")
        self.assertEqual(stats["vision"], "success")
        
        # Verify output files
        self.assertTrue(os.path.exists("data/raw_orders.json"))
        self.assertTrue(os.path.exists("data/report.json"))
        self.assertTrue(os.path.exists("data/report.txt"))
        
        # Verify memory updates
        self.assertTrue(os.path.exists(MEMORY_FILE))
        self.assertTrue(os.path.exists(STATE_FILE))
        
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state_content = f.read()
        self.assertIn("Idle", state_content)
        self.assertIn("Pipeline run finished successfully.", state_content)

    def test_pipeline_self_healing(self):
        """Verify that when a crawler selector fails, the self-healing mechanism corrects it and resumes execution."""
        # 1. Inject an invalid selector to force crawler fail
        with open(SELECTORS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "orders_table_rows": "table.non_existent_class tr",
                "orders_table_cells": "td"
            }, f)
            
        orchestrator = HermesOrchestrator(simulation=True)
        
        # Execute run - it should fail initially, self-heal, and complete successfully
        stats = asyncio.run(orchestrator.run_pipeline())
        
        # Verify self-healing details
        self.assertTrue(stats["healed"], "Self-healing should have been triggered and return True")
        self.assertEqual(stats["crawler"], "success", "Crawler should recover and complete successfully")
        self.assertEqual(stats["analyzer"], "success")
        
        # Ensure selectors were corrected back
        with open(SELECTORS_FILE, "r", encoding="utf-8") as f:
            selectors = json.load(f)
        self.assertEqual(selectors["orders_table_rows"], "table tbody tr")
        
        # Check MEMORY.md logs self-healing event
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            mem_content = f.read()
        self.assertIn("Self-healing successfully updated selector", mem_content)

if __name__ == "__main__":
    unittest.main()
