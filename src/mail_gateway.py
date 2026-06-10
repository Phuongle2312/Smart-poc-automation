"""
Phase 4: Outlook Mail Gateway
Enables remote operations via Outlook mail interface using SMTP/IMAP or MS Graph API.
Supports whitelist verification, email-based commands, and Human-in-the-loop approval.
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.agent_orchestrator import HermesOrchestrator, USER_FILE, STATE_FILE, MEMORY_FILE
from src.mail_sender import send_admin_email

load_dotenv()
logger = logging.getLogger("mail_gateway")

class OutlookMailGateway:
    def __init__(self, orchestrator: HermesOrchestrator = None):
        self.orchestrator = orchestrator or HermesOrchestrator()
        self.orchestrator.auto_approve = False # Gateway controls approval loop
        
        # Outlook configuration
        self.outlook_user = os.getenv("OUTLOOK_USER", "")
        self.outlook_pass = os.getenv("OUTLOOK_PASS", "")
        self.imap_server = os.getenv("IMAP_SERVER", "imap.office365.com")
        
        try:
            self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        except ValueError:
            self.imap_port = 993
            
        self.is_running = False
        self.whitelist = []
        self._load_whitelist()

    def _load_whitelist(self):
        """Loads whitelist emails from memory/USER.md JSON."""
        if os.path.exists(USER_FILE):
            try:
                with open(USER_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                # If USER.md starts with markdown headers, extract JSON or parse directly
                if content.startswith("{"):
                    data = json.loads(content)
                else:
                    # Look for JSON block in markdown
                    import re
                    match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                    else:
                        data = {}
                self.whitelist = data.get("whitelist_emails", [])
            except Exception as e:
                logger.error(f"Failed to parse whitelist from {USER_FILE}: {e}")
                self.whitelist = []
        
        # Add default admin email if whitelist is empty
        admin_email = os.getenv("ADMIN_EMAIL")
        if not self.whitelist and admin_email:
            self.whitelist = [admin_email]
            
        logger.info(f"Loaded whitelist emails: {self.whitelist}")

    def is_authorized(self, email_address: str) -> bool:
        """Verifies if the email sender address is whitelisted."""
        if not email_address:
            return False
        email_clean = email_address.strip().lower()
        authorized = email_clean in [w.strip().lower() for w in self.whitelist]
        if not authorized:
            logger.warning(f"Unauthorized email access attempt from: {email_address}")
            # Log warning event to system log file
            log_filename = f"logs/system_{datetime.now().strftime('%Y%m%d')}.log"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(log_filename, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] [WARNING] Unauthorized email access attempt from: {email_address}\n")
            except Exception:
                pass
        return authorized

    async def start(self):
        """Starts the Mail gateway loop or mock CLI listener if offline."""
        disable_mail = os.getenv("DISABLE_OUTBOUND_MAIL", "false").lower() == "true"
        
        if disable_mail or not self.outlook_user or not self.outlook_pass or self.outlook_user.upper() in ["DISABLED", "OFFLINE", "MOCK"]:
            logger.warning("Outlook mail gateway offline or missing credentials. Starting simulated CLI Email Gateway.")
            await self._run_mock_cli()
            return
            
        self.is_running = True
        logger.info("Outlook Mail Gateway started. Polling inbox every 30 seconds...")
        
        try:
            while self.is_running:
                await self._poll_emails()
                await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error in Mail Gateway polling loop: {e}")
            await self._run_mock_cli()

    async def stop(self):
        """Stops the mail gateway polling."""
        logger.info("Stopping Mail Gateway...")
        self.is_running = False

    async def _poll_emails(self):
        """Polls inbox via IMAP and processes new command or approval emails."""
        import imaplib
        import email
        from email.header import decode_header
        
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.outlook_user, self.outlook_pass)
            mail.select("inbox")
            
            # Search for unseen messages
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                return
                
            for num in messages[0].split():
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue
                    
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Get sender address
                from_header = msg.get("From", "")
                sender_email = email.utils.parseaddr(from_header)[1]
                
                # Decode subject
                subject_header = msg.get("Subject", "")
                subject, encoding = decode_header(subject_header)[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="replace")
                
                # Decode body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disp = str(part.get("Content-Disposition"))
                        if content_type == "text/plain" and "attachment" not in content_disp:
                            payload = part.get_payload(decode=True)
                            body = payload.decode(errors="replace")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="replace")
                
                # Process the email
                await self._process_received_email(sender_email, subject.strip(), body.strip())
                
                # Mark as seen
                mail.store(num, "+FLAGS", "\\Seen")
                
            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Failed to poll Outlook emails: {e}")

    async def _process_received_email(self, sender: str, subject: str, body: str):
        """Processes an incoming authorized email command or approval."""
        if not self.is_authorized(sender):
            return
            
        logger.info(f"Processing email from {sender} - Subject: {subject}")
        
        # 1. Check for commands
        if subject.startswith("[CMD]"):
            cmd = subject.replace("[CMD]", "").strip().upper()
            
            if cmd == "RUN_FULL":
                logger.info("Received RUN_FULL command email.")
                send_admin_email(
                    "🔄 [ACK] Hermes Pipeline Started", 
                    "Hermes Agent has received your command. Triggering pipeline G1 -> G2 -> G3..."
                )
                # Run pipeline asynchronously to not block email polling
                asyncio.create_task(self._execute_pipeline_and_respond(sender))
                
            elif cmd == "STATUS":
                logger.info("Received STATUS command email.")
                status = self.orchestrator.get_status()
                send_admin_email(
                    "📊 [STATUS] Hermes System State",
                    f"Here is the current system status details:\n\n{status}"
                )
                
            elif cmd == "REPORT":
                logger.info("Received REPORT command email.")
                report_text = self.orchestrator.get_last_report()
                report_json_path = "data/report.json"
                report_txt_path = "data/report.txt"
                
                send_admin_email(
                    "📋 [REPORT] Compliance Audit Summary",
                    f"Here is the latest compliance audit summary:\n\n{report_text}",
                    attachment_path=report_txt_path if os.path.exists(report_txt_path) else None
                )
                
            elif cmd == "STOP":
                logger.warning("Received STOP command email.")
                self.orchestrator.stop_pipeline()
                send_admin_email(
                    "🛑 [STOP] Pipeline Aborted",
                    "Immediate stop signal broadcasted to pipeline execution. Currently stopping processes."
                )
                
        # 2. Check for self-healing approval (reply to HEALING_APPROVAL)
        elif self.orchestrator.pending_approval and ("[HEALING_APPROVAL]" in subject or "RE:" in subject.upper() or "FW:" in subject.upper()):
            body_upper = body.upper()
            if "APPROVED" in body_upper:
                logger.info("Self-healing APPROVED by email response.")
                self.orchestrator.approval_result = "APPROVED"
                send_admin_email(
                    "✅ [HEALING] Selector Approved",
                    "Thank you. The proposed CSS selector modification has been approved and applied. Resuming crawler..."
                )
            elif "REJECTED" in body_upper:
                logger.warning("Self-healing REJECTED by email response.")
                self.orchestrator.approval_result = "REJECTED"
                send_admin_email(
                    "❌ [HEALING] Selector Rejected",
                    "The proposed CSS selector modification was rejected. Crawler aborted."
                )

    async def _execute_pipeline_and_respond(self, sender: str):
        """Runs the pipeline and sends the final report as an attachment."""
        try:
            results = await self.orchestrator.run_pipeline()
            report_txt = "data/report.txt"
            
            # Read report summary
            summary = ""
            if os.path.exists(report_txt):
                with open(report_txt, "r", encoding="utf-8") as f:
                    summary = f.read()
            else:
                summary = f"Pipeline execution completed. Results details:\n{json.dumps(results, indent=2)}"
                
            send_admin_email(
                "✅ [COMPLETED] Hermes Pipeline Run Results",
                f"The pipeline run completed successfully.\n\n{summary}",
                attachment_path=report_txt if os.path.exists(report_txt) else None
            )
        except Exception as e:
            logger.error(f"Error running pipeline from email command: {e}")
            send_admin_email(
                "❌ [ERROR] Hermes Pipeline Execution Failed",
                f"A critical error occurred while executing the pipeline: {e}"
            )

    # --- CLI Simulation Mode ---
    async def _run_mock_cli(self):
        """Simulates command input via standard input/logs for testing purposes."""
        print("======================================================================")
        print("          SIMULATED OUTLOOK EMAIL GATEWAY (Offline Mode)              ")
        print("Whitelisted senders: " + ", ".join(self.whitelist))
        print("Simulated Email subjects:                                             ")
        print("  - [CMD] RUN_FULL                                                    ")
        print("  - [CMD] STATUS                                                      ")
        print("  - [CMD] REPORT                                                      ")
        print("  - [CMD] STOP                                                        ")
        print("  - APPROVED  (for pending self-healing approvals)                    ")
        print("  - REJECTED  (for pending self-healing approvals)                    ")
        print("Type /exit to shut down gateway.                                      ")
        print("======================================================================")
        
        if not sys.stdin.isatty():
            logger.info("Non-interactive terminal detected. Skipping CLI command prompt loop.")
            # Keep active to represent daemon running
            await asyncio.sleep(2)
            return

        try:
            while True:
                # Read command asynchronously
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(None, input, "mail-gateway> ")
                line = user_input.strip()
                
                if not line:
                    continue
                    
                if line == "/exit":
                    print("Exiting Mail simulation.")
                    break
                    
                # Simulate receiving an email from whitelisted sender
                sender = self.whitelist[0] if self.whitelist else "admin_account@yourcompany.com"
                
                # If there's a pending self-healing approval
                if self.orchestrator.pending_approval:
                    if "APPROVED" in line.upper():
                        print(f"[MOCK EMAIL Received] From: {sender} | Subject: Re: [HEALING_APPROVAL] | Body: APPROVED")
                        await self._process_received_email(sender, "Re: [HEALING_APPROVAL]", "APPROVED")
                    elif "REJECTED" in line.upper():
                        print(f"[MOCK EMAIL Received] From: {sender} | Subject: Re: [HEALING_APPROVAL] | Body: REJECTED")
                        await self._process_received_email(sender, "Re: [HEALING_APPROVAL]", "REJECTED")
                    else:
                        print("Pending approval active. Please type 'APPROVED' or 'REJECTED'.")
                else:
                    if line.upper() in ["/RUN_FULL", "RUN_FULL", "[CMD] RUN_FULL"]:
                        print(f"[MOCK EMAIL Received] From: {sender} | Subject: [CMD] RUN_FULL")
                        await self._process_received_email(sender, "[CMD] RUN_FULL", "")
                    elif line.upper() in ["/STATUS", "STATUS", "[CMD] STATUS"]:
                        print(f"[MOCK EMAIL Received] From: {sender} | Subject: [CMD] STATUS")
                        await self._process_received_email(sender, "[CMD] STATUS", "")
                    elif line.upper() in ["/REPORT", "REPORT", "[CMD] REPORT"]:
                        print(f"[MOCK EMAIL Received] From: {sender} | Subject: [CMD] REPORT")
                        await self._process_received_email(sender, "[CMD] REPORT", "")
                    elif line.upper() in ["/STOP", "STOP", "[CMD] STOP"]:
                        print(f"[MOCK EMAIL Received] From: {sender} | Subject: [CMD] STOP")
                        await self._process_received_email(sender, "[CMD] STOP", "")
                    else:
                        print(f"[MOCK EMAIL Received] From: {sender} | Subject: [EMAIL] {line}")
                        await self._process_received_email(sender, line, "")
        except KeyboardInterrupt:
            print("\nShutting down simulation...")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gateway = OutlookMailGateway()
    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        pass
