from jose import jwt
from datetime import datetime, timedelta
import qrcode
from pathlib import Path

from services.api.app.core.config import get_settings

settings = get_settings()

SECRET_KEY = settings.CHECKIN_SECRET
ALGORITHM = "HS256"

QR_DIR = Path("generated_qr")


def generate_checkin_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=24)

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_checkin_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def generate_qr(token: str, booking_id: str) -> str:
    QR_DIR.mkdir(exist_ok=True)

    file_path = QR_DIR / f"{booking_id}.png"

    img = qrcode.make(token)
    img.save(file_path)  # type: ignore

    return str(file_path)