import smtplib
from email.message import EmailMessage

from app.config import settings


async def send_confirmation_email(to: str, subject: str, html: str) -> dict:
    """
    Sends the confirmation email via standard SMTP instead of Resend.
    If SMTP_SERVER is not configured, it will simulate sending by printing to console.
    """
    if not settings.SMTP_SERVER:
        print("\n" + "="*50)
        print("SIMULATING EMAIL SEND (SMTP not configured):")
        print(f"To: {to} (from {settings.EMAIL_FROM})")
        print(f"Subject: {subject}")
        print("-" * 50)
        print(html)
        print("="*50 + "\n")
        return {"status": "simulated"}

    msg = EmailMessage()
    msg.set_content(html, subtype="html")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to

    # We send synchronously since smtplib does not have an async API
    try:
        if settings.SMTP_TLS:
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.send_message(msg)
                    
        return {"status": "sent"}
    except Exception as e:
        print(f"Failed to send email via SMTP: {e}")
        # Re-raise so the queue knows the job failed and can retry it
        raise e
