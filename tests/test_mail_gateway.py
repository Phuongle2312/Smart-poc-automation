"""
Unit tests for Phase 4 OutlookMailGateway.
Verifies whitelisting, command processing, and Human-in-the-loop approvals.
"""

import os
import sys
import json
import unittest
import asyncio
from unittest.mock import MagicMock, patch

# Ensure project root in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.agent_orchestrator import HermesOrchestrator, USER_FILE
from src.mail_gateway import OutlookMailGateway

class TestMailGateway(unittest.TestCase):
    def setUp(self):
        # Create a mock USER.md whitelist
        os.makedirs("memory", exist_ok=True)
        self.whitelist_data = {
            "whitelist_emails": [
                "authorized_admin@company.com",
                "supervisor@company.com"
            ]
        }
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(self.whitelist_data, f, indent=2)

        self.orchestrator = HermesOrchestrator(simulation=True)
        async def mock_run():
            return {"status": "success"}
        self.orchestrator.run_pipeline = MagicMock(side_effect=mock_run)
        self.gateway = OutlookMailGateway(orchestrator=self.orchestrator)

    def tearDown(self):
        if os.path.exists(USER_FILE):
            os.remove(USER_FILE)

    def test_whitelist_authorization(self):
        """Verify that only whitelisted emails are authorized."""
        self.assertTrue(self.gateway.is_authorized("authorized_admin@company.com"))
        self.assertTrue(self.gateway.is_authorized("supervisor@company.com"))
        self.assertTrue(self.gateway.is_authorized("  SUPERVISOR@company.com  ")) # Whitespace and casing
        
        self.assertFalse(self.gateway.is_authorized("intruder@gmail.com"))
        self.assertFalse(self.gateway.is_authorized(""))
        self.assertFalse(self.gateway.is_authorized(None))

    @patch('src.mail_gateway.send_admin_email')
    def test_unauthorized_email_warning(self, mock_send_email):
        """Verify that unauthorized emails are ignored and log warnings."""
        import time
        log_file = f"logs/system_{time.time():.0f}.log"
        # We can mock system log date or just run normal check
        # Run process email with unauthorized address
        asyncio.run(self.gateway._process_received_email("intruder@gmail.com", "[CMD] RUN_FULL", ""))
        
        # Verify run_pipeline was NOT called
        self.orchestrator.run_pipeline.assert_not_called()
        mock_send_email.assert_not_called()

    @patch('src.mail_gateway.send_admin_email')
    def test_status_command(self, mock_send_email):
        """Verify that [CMD] STATUS retrieves status and responds."""
        asyncio.run(self.gateway._process_received_email("authorized_admin@company.com", "[CMD] STATUS", ""))
        
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        self.assertIn("[STATUS]", args[0])
        self.assertIn("Current State", args[1])

    @patch('src.mail_gateway.send_admin_email')
    def test_run_full_command(self, mock_send_email):
        """Verify that [CMD] RUN_FULL starts the pipeline run."""
        # Use helper run since _process_received_email spawns an async task
        asyncio.run(self.gateway._process_received_email("authorized_admin@company.com", "[CMD] RUN_FULL", ""))
        
        # Give a small slice to event loop to run tasks
        asyncio.run(asyncio.sleep(0.1))
        
        # run_pipeline should be called
        self.orchestrator.run_pipeline.assert_called_once()
        # Initial ack email should be sent
        self.assertTrue(mock_send_email.called)

    @patch('src.mail_gateway.send_admin_email')
    def test_self_healing_approval_flow(self, mock_send_email):
        """Verify whitelisted email APPROVED / REJECTED flow for pending self-healing."""
        # Set pending approval state
        self.orchestrator.pending_approval = {"key": "test_selector"}
        self.orchestrator.approval_result = None

        # Simulate APPROVED response
        asyncio.run(self.gateway._process_received_email(
            "authorized_admin@company.com", 
            "Re: [HEALING_APPROVAL] Đề xuất sửa đổi Selector", 
            "APPROVED - please proceed"
        ))

        # Check result
        self.assertEqual(self.orchestrator.approval_result, "APPROVED")
        mock_send_email.assert_called_with(
            "✅ [HEALING] Selector Approved",
            "Thank you. The proposed CSS selector modification has been approved and applied. Resuming crawler..."
        )

        # Reset and simulate REJECTED response
        self.orchestrator.pending_approval = {"key": "test_selector"}
        self.orchestrator.approval_result = None
        mock_send_email.reset_mock()

        asyncio.run(self.gateway._process_received_email(
            "supervisor@company.com", 
            "Re: [HEALING_APPROVAL]", 
            "REJECTED - do not update"
        ))

        self.assertEqual(self.orchestrator.approval_result, "REJECTED")
        mock_send_email.assert_called_with(
            "❌ [HEALING] Selector Rejected",
            "The proposed CSS selector modification was rejected. Crawler aborted."
        )

if __name__ == "__main__":
    unittest.main()
