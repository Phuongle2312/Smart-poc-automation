"""
Utility module to send SMTP email notifications to the Admin.
Uses credentials and SMTP configuration from environment variables.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mail_sender")

def send_admin_email(subject: str, body: str, attachment_path: str = None) -> bool:
    """
    Sends an email to the administrator (ADMIN_EMAIL) using SMTP configuration from .env.
    If credentials are not fully configured, it logs the email content and returns True (simulating success).
    """
    smtp_user = os.getenv("OUTLOOK_USER")
    smtp_pass = os.getenv("OUTLOOK_PASS")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.office365.com")
    admin_email = os.getenv("ADMIN_EMAIL")
    
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        smtp_port = 587

    if not smtp_user or not smtp_pass or not admin_email:
        logger.warning("[MOCK EMAIL] SMTP credentials or Admin Email not fully configured. Logging email details:")
        logger.warning(f"To: {admin_email or 'Not Set'}")
        logger.warning(f"Subject: {subject}")
        logger.warning(f"Body: {body}")
        if attachment_path:
            logger.warning(f"Attachment: {attachment_path}")
        return True

    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = admin_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Attach image/file if specified
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                file_data = f.read()
            
            # Check if it's an image
            if attachment_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                img_part = MIMEImage(file_data, name=os.path.basename(attachment_path))
                msg.attach(img_part)
            else:
                # General attachment
                from email.mime.base import MIMEBase
                from email import encoders
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(attachment_path)}"')
                msg.attach(part)
                
        # Connect and send
        logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, admin_email, msg.as_string())
        server.quit()
        logger.info(f"Email successfully sent to {admin_email} with subject '{subject}'.")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to admin: {e}")
        # Return True in simulation/test context to avoid breaking execution
        return False
