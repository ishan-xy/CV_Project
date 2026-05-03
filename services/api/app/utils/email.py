from email.message import EmailMessage
import smtplib

from services.api.app.core.config import get_settings

settings = get_settings()


def send_checkin_email(to_email: str, qr_path: str):
    msg = EmailMessage()
    msg["Subject"] = "Your Check-in QR Code"
    msg["From"] = settings.SMTP_USERNAME
    msg["To"] = to_email

    msg.set_content("Scan the attached QR code at the room to unlock it.")

    with open(qr_path, "rb") as f:
        img_data = f.read()

    msg.add_attachment(
        img_data,
        maintype="image",
        subtype="png",
        filename="checkin_qr.png"
    )

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)