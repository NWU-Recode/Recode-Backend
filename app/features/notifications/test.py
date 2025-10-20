import os
from app.features.notifications.repository import _send_email_sync

_send_email_sync(
    smtp_host=os.getenv("SMTP_HOST"),
    smtp_port=int(os.getenv("SMTP_PORT")),
    smtp_user=os.getenv("SMTP_USER"),
    smtp_pass=os.getenv("SMTP_PASS"),
    to_email="artinadutjoammakoma@gmail.com",
    subject="SMTP Test",
    body="This is a test email from NWU Recode Notifications."
)
