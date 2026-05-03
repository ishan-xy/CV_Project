import cv2
from pyzbar.pyzbar import decode
from jose import jwt, JWTError
from datetime import date
import os
import time
from dotenv import load_dotenv
import threading
import subprocess


load_dotenv()

SECRET_KEY = os.getenv("CHECKIN_SECRET")
ALGORITHM = "HS256"

PROCESS_FPS = 6
PROCESS_INTERVAL = 1.0 / PROCESS_FPS

last_process_time = 0

last_result = "SCAN QR"
last_payload = None
last_color = (200, 200, 200)

last_data = None
last_beeped_data = None

same_count = 0
prev_data = None
STABILITY_REQUIRED = 3


def play_sound(success: bool):
    def run():
        if success:
            subprocess.run(
                ["afplay", "/System/Library/Sounds/Glass.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            subprocess.run(
                ["afplay", "/System/Library/Sounds/Basso.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    threading.Thread(target=run, daemon=True).start()


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        check_in = date.fromisoformat(payload["check_in"])
        check_out = date.fromisoformat(payload["check_out"])
        today = date.today()

        if today < check_in:
            return False, "TOO EARLY", payload

        if today > check_out:
            return False, "EXPIRED", payload

        return True, "ACCESS GRANTED", payload

    except JWTError:
        return False, "INVALID QR", None
    except Exception:
        return False, "ERROR", None


cap = cv2.VideoCapture(0)

print("Press 'q' to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    now = time.time()

    if now - last_process_time >= PROCESS_INTERVAL:
        last_process_time = now

        decoded = decode(frame)

        if decoded:
            obj = decoded[0]
            data = obj.data.decode("utf-8")

            if data == prev_data:
                same_count += 1
            else:
                same_count = 1
                prev_data = data

            if same_count >= STABILITY_REQUIRED:
                if data != last_data:
                    is_valid, message, payload = verify_token(data)

                    last_data = data
                    last_result = message
                    last_payload = payload

                    if is_valid:
                        last_color = (0, 200, 0)
                    else:
                        last_color = (0, 0, 200)

                    # 🔊 play sound once per QR
                    if data != last_beeped_data:
                        play_sound(is_valid)
                        last_beeped_data = data

    overlay = frame.copy()
    h, w, _ = frame.shape

    cv2.rectangle(overlay, (0, 0), (w, 100), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)

    cv2.putText(
        frame,
        last_result,
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        last_color,
        3
    )

    if last_payload:
        name = last_payload.get("name", "")
        room = str(last_payload.get("rooms", ""))

        cv2.putText(
            frame,
            f"{name} | Room {room}",
            (20, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

    cv2.rectangle(frame, (0, 0), (w, h), last_color, 4)

    cv2.imshow("Smart Lock Scanner", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()