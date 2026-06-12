"""
Phase 3: Actuator controller (RoboClaw Serial)
Manages serial communication with RoboClaw motor controllers for rejecting items
and triggering alarms. Supports local simulation mode.
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
log_filename = f"logs/system_{time.strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("actuator")

class RoboClawActuator:
    def __init__(self, port: str = None, baudrate: int = 115200, simulation: bool = None):
        """
        Initializes the RoboClaw Actuator.
        If simulation is True, commands are only logged to console.
        """
        # Read from environment variables if not specified
        self.port = port or os.getenv("ROBOCLAW_PORT", "COM3")
        
        try:
            self.baudrate = int(os.getenv("ROBOCLAW_BAUDRATE", str(baudrate)))
        except ValueError:
            self.baudrate = baudrate
            
        # Check HW_MODE first, then fallback to ROBOCLAW_SIMULATION
        if simulation is not None:
            self.simulation = simulation
        else:
            hw_mode_env = os.getenv("HW_MODE")
            if hw_mode_env is not None:
                self.simulation = hw_mode_env.lower() != "true"
            else:
                self.simulation = os.getenv("ROBOCLAW_SIMULATION", "true").lower() == "true"
        
        self.client = None
        
        if not self.simulation:
            logger.info(f"Attempting to initialize hardware RoboClaw on port {self.port} at {self.baudrate} baud...")
            try:
                # Dynamic import to avoid crash if roboclaw is not installed
                from roboclaw import Roboclaw  # type: ignore
                self.client = Roboclaw(self.port, self.baudrate)
                if self.client.Open():
                    logger.info("Successfully connected to RoboClaw hardware.")
                else:
                    raise Exception(f"Could not open serial port {self.port}")
            except Exception as e:
                # Catching SerialException or general exception
                logger.warning(f"Hardware connection error: {e}. Falling back to Simulation Mode.")
                self.simulation = True
                
                # Send email alert to Admin
                try:
                    from src.mail_sender import send_admin_email
                    subject = "⚠️ [HARDWARE ERROR] RoboClaw Serial Connection Failed"
                    body = (
                        f"System warning: Failed to initialize RoboClaw hardware on port {self.port}.\n"
                        f"Error details: {e}\n\n"
                        "The system has automatically fallen back to Simulation Mode to ensure operations continue."
                    )
                    send_admin_email(subject, body)
                except Exception as mail_err:
                    logger.error(f"Failed to send connection error email alert: {mail_err}")
        else:
            logger.info("RoboClaw Actuator initialized in Simulation Mode.")

    def trigger_reject_arm(self) -> bool:
        """
        Kích hoạt cánh tay gạt sản phẩm lỗi
        """
        if self.simulation:
            try:
                logger.info("[MOCK] RoboClaw Signal: REJECT - Kích hoạt cánh tay gạt!")
                print("[MOCK] RoboClaw Signal: REJECT - Kích hoạt cánh tay gạt!")
            except UnicodeEncodeError:
                logger.info("[MOCK] RoboClaw Signal: REJECT - Kich hoat canh tay gat!")
                print("[MOCK] RoboClaw Signal: REJECT - Kich hoat canh tay gat!")
            return True
            
        try:
            address = 0x80
            # Gửi lệnh điều khiển Motor 1 chạy tiến trong 500ms rồi lùi về vị trí cũ
            logger.info("Sending hardware command: ForwardM1 to reject item.")
            self.client.ForwardM1(address, 64) # Chạy tiến nửa công suất
            time.sleep(0.5)
            logger.info("Sending hardware command: BackwardM1 to return arm.")
            self.client.BackwardM1(address, 64) # Chạy lùi nửa công suất
            time.sleep(0.5)
            self.client.ForwardM1(address, 0) # Dừng motor
            logger.info("Actuator reject sequence completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to execute hardware reject: {e}")
            return False

    def trigger_reject(self) -> bool:
        """
        Triggers the reject mechanism.
        Returns True if successful, False otherwise.
        """
        return self.trigger_reject_arm()

    def trigger_alarm(self, status: bool = True) -> bool:
        """
        Turns the alarm indicator ON or OFF.
        """
        action = "ON" if status else "OFF"
        if self.simulation:
            logger.info(f"[MOCK] RoboClaw alarm: {action}")
            print(f"[MOCK] RoboClaw alarm: {action}")
            return True
            
        try:
            address = 0x80
            speed = 127 if status else 0
            logger.info(f"Sending hardware command: Set alarm indicator {action} (Speed: {speed}).")
            self.client.ForwardM2(address, speed)
            return True
        except Exception as e:
            logger.error(f"Failed to control hardware alarm: {e}")
            return False

if __name__ == "__main__":
    # Test script runs actuator in simulation mode by default
    actuator = RoboClawActuator(simulation=True)
    actuator.trigger_alarm(True)
    time.sleep(0.5)
    actuator.trigger_reject()
    time.sleep(0.5)
    actuator.trigger_alarm(False)
