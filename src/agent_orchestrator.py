"""
Phase 4: Hermes Agent Orchestrator
Manages and orchestrates the full operational workflow G1 -> G2 -> G3 -> G4.
Includes memory updates, state tracking, self-healing selector logic, and circuit breaker.
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is in system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.crawler import run_crawler, SELECTORS_FILE
from src.analyzer import run_analysis, REPORT_TXT_FILE
from src.vision_inspector import VisionInspector
from src.actuator import RoboClawActuator

load_dotenv()

# Setup logging
os.makedirs("logs", exist_ok=True)
os.makedirs("memory", exist_ok=True)

log_filename = f"logs/system_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("orchestrator")

MEMORY_FILE = "memory/MEMORY.md"
USER_FILE = "memory/USER.md"
STATE_FILE = "memory/SYSTEM_STATE.md"
RAW_ORDERS_FILE = "data/raw_orders.json"

class HermesOrchestrator:
    def __init__(self, simulation: bool = True):
        self.simulation = simulation
        self.is_running = False
        self.stop_requested = False
        self.auto_approve = True  # Default to True for automated tests and standalone runs
        self.pending_approval = None
        self.approval_result = None
        self._healing_attempts = 0
        self._last_alert_times: dict = {}  # {alert_type: datetime} for dedup
        self._init_memory_files()
        self.cleanup_expired_data()

    def _init_memory_files(self):
        """Initializes memory files with SRS-defined schemas if they do not exist."""
        if not os.path.exists(USER_FILE) or os.path.getsize(USER_FILE) < 20:
            admin_email = os.getenv("ADMIN_EMAIL", "admin_account@yourcompany.com")
            content = (
                "# USER CONFIG\n"
                "whitelist_emails:\n"
                f"  - {admin_email}\n"
                "email_rate_limit_seconds: 60\n"
                "max_healing_attempts: 3\n"
            )
            with open(USER_FILE, "w", encoding="utf-8") as f:
                f.write(content)

        if not os.path.exists(MEMORY_FILE) or os.path.getsize(MEMORY_FILE) < 20:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                f.write("# OPERATION HISTORY\n\nTracks execution history and self-healing events of Hermes Agent.\n")

        if not os.path.exists(STATE_FILE) or os.path.getsize(STATE_FILE) < 20:
            self._update_system_state("IDLE", "none", "")

    def cleanup_expired_data(self):
        """
        Deletes files in data/raw_orders.json and data/defects/*.jpg (or other files)
        that are older than 7 days, to comply with data retention rules.
        """
        logger.info("Running expired data retention cleanup...")
        now = time.time()
        retention_period = 7 * 24 * 60 * 60 # 7 days in seconds
        
        # 1. Check raw_orders.json
        if os.path.exists(RAW_ORDERS_FILE):
            file_age = now - os.path.getmtime(RAW_ORDERS_FILE)
            if file_age > retention_period:
                try:
                    os.remove(RAW_ORDERS_FILE)
                    logger.info(f"Deleted expired file: {RAW_ORDERS_FILE} (age: {file_age/(24*3600):.1f} days)")
                except Exception as e:
                    logger.error(f"Failed to delete expired file {RAW_ORDERS_FILE}: {e}")
                    
        # 2. Check data/defects/ directory
        defects_dir = "data/defects"
        if os.path.exists(defects_dir):
            try:
                for file in os.listdir(defects_dir):
                    file_path = os.path.join(defects_dir, file)
                    if os.path.isfile(file_path):
                        file_age = now - os.path.getmtime(file_path)
                        if file_age > retention_period:
                            os.remove(file_path)
                            logger.info(f"Deleted expired defect file: {file_path} (age: {file_age/(24*3600):.1f} days)")
            except Exception as e:
                logger.error(f"Failed to run data/defects retention cleanup: {e}")

    def _update_system_state(self, status: str, active_task: str, error_message: str = ""):
        """Updates SYSTEM_STATE.md using the SRS-defined schema."""
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        content = (
            "# SYSTEM STATE\n"
            f"status: {status}\n"
            f"last_updated: {timestamp}\n"
            f"active_task: {active_task}\n"
            f"error_message: {error_message}\n"
            f"healing_attempts: {self._healing_attempts}\n"
        )
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"System State updated: {status} / task={active_task}")

    def _append_to_memory(self, log_entry: str):
        """Appends a timestamped section entry to MEMORY.md using SRS schema format."""
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n## [{timestamp}] {log_entry}\n")

    def _send_alert_deduped(self, alert_type: str, subject: str, body: str, attachment_path: str = None):
        """Sends an admin email alert, suppressing duplicates within 30 minutes."""
        from src.mail_sender import send_admin_email
        dedup_window_seconds = 30 * 60  # 30 minutes
        last_sent = self._last_alert_times.get(alert_type)
        if last_sent:
            elapsed = (datetime.now() - last_sent).total_seconds()
            if elapsed < dedup_window_seconds:
                logger.warning(
                    f"Alert '{alert_type}' suppressed (sent {elapsed:.0f}s ago, dedup window={dedup_window_seconds}s)."
                )
                return
        send_admin_email(subject, body, attachment_path=attachment_path)
        self._last_alert_times[alert_type] = datetime.now()

    def get_status(self) -> str:
        """Reads current system state from state file."""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return "Unknown state."

    def get_last_report(self) -> str:
        """Reads and returns the latest text compliance report."""
        if os.path.exists(REPORT_TXT_FILE):
            with open(REPORT_TXT_FILE, "r", encoding="utf-8") as f:
                return f.read()
        return "No compliance report found. Run the pipeline first."

    def stop_pipeline(self):
        """Signals the pipeline to abort."""
        logger.warning("Pipeline stop requested.")
        self.stop_requested = True
        self._update_system_state("IDLE", "none", "Pipeline stopped by user command.")

    async def self_heal_selector(self, error_msg: str) -> bool:
        """
        Attempts self-healing on CSS selectors.
        Simulates parsing faulty HTML, identifying the table structure, and rewriting data/selectors.json.
        """
        logger.warning(f"Self-healing mechanism activated! Error: {error_msg}")
        self._update_system_state("HEALING", "self_healing", error_msg[:200])
        self._append_to_memory(f"Self-healing triggered — crawler failure: {error_msg}")
        
        # Read current selectors
        current_row = "table tbody tr"
        if os.path.exists(SELECTORS_FILE):
            try:
                with open(SELECTORS_FILE, "r", encoding="utf-8") as f:
                    selectors = json.load(f)
                    current_row = selectors.get("orders_table_rows", "table tbody tr")
            except Exception:
                pass
                
        # Simulate LLM analysis of HTML DOM.
        new_row = "table tbody tr"
        new_cells = "td"
        
        logger.info(f"LLM Analysing DOM layout... Found table element. Suggesting row selector: '{new_row}'")
        
        # Send proposal email / update pending approval
        try:
            from src.mail_sender import send_admin_email
            
            diff_text = f"""
<<<<=== SELECTOR CORRECTION ===>>>>
- row_selector = "{current_row}"
+ row_selector = "{new_row}"
<<<<===========================>>>>
"""
            subject = "🚨 [HEALING_APPROVAL] Đề xuất sửa đổi Selector nút Login"
            body = (
                f"Crawler failed due to: {error_msg}\n\n"
                f"LLM proposed fix:\n{diff_text}\n\n"
                "Please reply with 'APPROVED' to apply this change, or 'REJECTED' to abort."
            )
            
            self.pending_approval = {
                "selectors_file": SELECTORS_FILE,
                "current_row": current_row,
                "new_row": new_row,
                "new_cells": new_cells
            }
            self.approval_result = None
            
            # Send email proposal with mock attachment if exists
            mock_screenshot = "logs/debug_screenshot.png"
            if not os.path.exists(mock_screenshot):
                os.makedirs("logs", exist_ok=True)
                with open(mock_screenshot, "wb") as f:
                    f.write(b"mock screenshot data")
            
            send_admin_email(subject, body, attachment_path=mock_screenshot)
            
            if self.auto_approve:
                logger.info("auto_approve is active. Bypassing human approval and auto-approving.")
                self.approval_result = "APPROVED"
            else:
                logger.info("Waiting for admin approval response via email...")
                # Poll approval_result
                while self.approval_result is None:
                    if self.stop_requested:
                        self.approval_result = "REJECTED"
                        break
                    await asyncio.sleep(2)
                    
            if self.approval_result == "APPROVED":
                # Backup current selectors before overwriting
                bak_file = SELECTORS_FILE + ".bak"
                if os.path.exists(SELECTORS_FILE):
                    import shutil
                    shutil.copy2(SELECTORS_FILE, bak_file)
                    logger.info(f"Backed up current selectors to {bak_file}")

                try:
                    with open(SELECTORS_FILE, "w", encoding="utf-8") as f:
                        json.dump({
                            "orders_table_rows": new_row,
                            "orders_table_cells": new_cells
                        }, f, indent=4)
                    logger.info("Selectors configuration updated successfully.")
                    self._healing_attempts += 1
                    self._append_to_memory(
                        f"Self-healing updated selector '{current_row}' -> '{new_row}' (attempt #{self._healing_attempts})"
                    )
                except Exception as write_err:
                    logger.error(f"Failed to write new selectors: {write_err}. Restoring backup.")
                    if os.path.exists(bak_file):
                        shutil.copy2(bak_file, SELECTORS_FILE)
                        logger.info("Restored selectors from backup.")
                    self.pending_approval = None
                    self.approval_result = None
                    return False

                self.pending_approval = None
                self.approval_result = None
                return True
            else:
                logger.error("Self-healing modification was REJECTED or pipeline was stopped.")
                self.pending_approval = None
                self.approval_result = None
                return False
                
        except Exception as e:
            logger.error(f"Self-healing failed: {e}")
            self.pending_approval = None
            self.approval_result = None
            return False

    async def run_pipeline(self) -> dict:
        """
        Orchestrates the entire G1 -> G2 -> G3 pipeline with self-healing and circuit breakers.
        """
        if self.is_running:
            logger.warning("Pipeline is already running.")
            return {"status": "busy", "message": "Pipeline already active"}
            
        self.is_running = True
        self.stop_requested = False
        self.cleanup_expired_data()
        self._update_system_state("RUNNING_CRAWLER", "run_full", "")
        self._append_to_memory("Started pipeline execution (RUN_FULL).")
        
        stats = {
            "crawler": "failed",
            "analyzer": "skipped",
            "vision": "skipped",
            "healed": False
        }
        
        try:
            # ----------------------------------------------------
            # Phase 1: Crawler with Self-Healing Retry Loop
            # ----------------------------------------------------
            max_attempts = 3
            attempt = 0
            crawler_success = False
            
            while attempt < max_attempts and not crawler_success and not self.stop_requested:
                attempt += 1
                logger.info(f"Crawler attempt {attempt}/{max_attempts}...")
                try:
                    await run_crawler()
                    crawler_success = True
                    stats["crawler"] = "success"
                    logger.info("Crawler executed successfully.")
                except Exception as e:
                    logger.error(f"Crawler execution error on attempt {attempt}: {e}")
                    # Trigger self-healing
                    if attempt < max_attempts:
                        healed = await self.self_heal_selector(str(e))
                        stats["healed"] = healed
                        if healed:
                            logger.info("Retrying Crawler with updated selectors...")
                            continue
                    # Circuit breaker triggered
                    logger.critical("Circuit breaker activated for Phase 1. Aborting run.")
                    self._update_system_state("ERROR", "none", f"Crawler failed after {attempt} attempts: {e}")
                    self._append_to_memory(f"Pipeline aborted — Crawler failed after {attempt} attempts: {e}")
                    return stats

            if self.stop_requested:
                return stats
                
            # ----------------------------------------------------
            # Phase 2: RAG Compliance Analysis
            # ----------------------------------------------------
            self._update_system_state("ANALYZING_RAG", "run_full", "")
            logger.info("Running Phase 2 Compliance Analyzer...")
            try:
                run_analysis()
                stats["analyzer"] = "success"
                logger.info("Analyzer executed successfully.")
            except Exception as e:
                logger.error(f"Analyzer failed: {e}")
                self._update_system_state("ERROR", "none", str(e))
                self._append_to_memory(f"Pipeline aborted — Analyzer failed: {e}")
                return stats
                
            if self.stop_requested:
                return stats
                
            # ----------------------------------------------------
            # Phase 3: Vision Inspection (Simulation / Live)
            # ----------------------------------------------------
            self._update_system_state("RUNNING_CRAWLER", "run_full", "")
            logger.info("Running Phase 3 Vision Inspector...")
            try:
                # Read crawled orders
                if os.path.exists(RAW_ORDERS_FILE):
                    with open(RAW_ORDERS_FILE, "r", encoding="utf-8") as f:
                        orders = json.load(f)
                else:
                    orders = []
                    
                actuator = RoboClawActuator(simulation=self.simulation)
                inspector = VisionInspector(simulation=self.simulation, actuator=actuator)
                
                os.makedirs("data/test_runs", exist_ok=True)
                
                defects_found = 0
                for order in orders:
                    if self.stop_requested:
                        break
                        
                    order_id = order.get("order_id", "UNKNOWN")
                    vendor = order.get("vendor", "").lower()
                    
                    # For simulating realistic defect checking,
                    # we designate ORD-2026-004 (or orders with negative/invalid data) as defective.
                    # We create mock images on-the-fly and pass them to inspector.
                    img_path = f"data/test_runs/product_{order_id}.jpg"
                    if "invalid" in vendor or "sino" in vendor or order.get("total_amount", 0) <= 0:
                        # Make this filename trigger a simulated defect
                        img_path = f"data/test_runs/product_{order_id}_defect.jpg"
                        
                    with open(img_path, "wb") as f:
                        f.write(b"mock camera image data")
                        
                    # Run CV inspection
                    inspection_result = inspector.inspect_image(img_path)
                    
                    # Clean up the run file
                    if os.path.exists(img_path):
                        try:
                            os.remove(img_path)
                        except Exception:
                            pass
                            
                    if inspection_result.get("has_defect", False):
                        defects_found += 1
                        
                stats["vision"] = "success"
                logger.info(f"Vision inspection completed. Defected items rejected: {defects_found}")
                self._append_to_memory(f"Pipeline run completed successfully. Checked {len(orders)} items. Rejected: {defects_found}")
                
                self._update_system_state("IDLE", "none", "")
                
            except Exception as e:
                logger.error(f"Vision inspection failed: {e}")
                self._update_system_state("ERROR", "none", str(e))
                self._append_to_memory(f"Pipeline warning — Vision failed: {e}")
                stats["vision"] = "warning"
                
            return stats
            
        finally:
            self.is_running = False

if __name__ == "__main__":
    orchestrator = HermesOrchestrator()
    asyncio.run(orchestrator.run_pipeline())
