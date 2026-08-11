"""Optional email via Gmail SMTP. No-op unless GMAIL_USER/GMAIL_APP_PASSWORD/DIGEST_TO set.

Setup: enable 2FA on the Gmail account, create an App Password
(https://myaccount.google.com/apppasswords) and store it as the GMAIL_APP_PASSWORD secret.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send(subject, text_body, html_body):
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("DIGEST_TO") or user
    if not (user and pw and to):
        print("[email] Gmail secrets not set; skipping send (digest saved to file).")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pw)
            s.sendmail(user, [addr.strip() for addr in to.split(",")], msg.as_string())
        print(f"[email] sent to {to}")
        return True
    except Exception as e:
        print(f"[email] send failed: {e}")
        return False
