import smtplib
import os
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)

ALERT_FROM = os.getenv("ALERT_FROM_EMAIL", "")
ALERT_TO = os.getenv("ALERT_TO_EMAIL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def send_alert(name: str, url: str, is_up: bool):
    if not all([ALERT_FROM, ALERT_TO, SMTP_PASSWORD]):
        logger.info("Alert skipped (no email config): %s is %s", name, "UP" if is_up else "DOWN")
        return

    subject = f"[PulseCheck] {'RECOVERED' if is_up else 'DOWN'}: {name}"
    body = f"{'✅ Recovered' if is_up else '🔴 Down'}: {name}\nURL: {url}"

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = ALERT_FROM
        msg["To"] = ALERT_TO
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(ALERT_FROM, SMTP_PASSWORD)
            smtp.send_message(msg)
        logger.info("Alert sent: %s", subject)
    except Exception as e:
        logger.error("Failed to send alert: %s", e)
