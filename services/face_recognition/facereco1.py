import cv2
import numpy as np
import os
import json
from pathlib import Path
from datetime import datetime
from retinaface import RetinaFace

from keras.models import Sequential
from keras.layers import Dense, Dropout, BatchNormalization, Flatten
from keras.applications.efficientnet import EfficientNetB7, preprocess_input


BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "models" / "best_model.weights.h5"
UPLOADS_DIR = BASE_DIR / "services" / "api" / "uploads"
BOOKING_INDEX_PATH = BASE_DIR / "booking_index.json"
LOG_FILE = BASE_DIR / "recognition_scores.log"

def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def start_new_session():
    separator = "\n" + "=" * 80 + "\n"
    separator += f"NEW SESSION STARTED: {datetime.now()}\n"
    separator += "=" * 80 + "\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(separator)

start_new_session()

with open(BOOKING_INDEX_PATH, "r") as f:
    booking_index = json.load(f)

def get_embedding_model(input_shape=(128, 128, 3), num_layers_to_unfreeze=25):
    base_model = EfficientNetB7(
        weights="imagenet",
        input_shape=input_shape,
        include_top=False,
        pooling="avg"
    )

    for i in range(len(base_model.layers) - num_layers_to_unfreeze):
        base_model.layers[i].trainable = False

    model = Sequential([
        base_model,
        Flatten(),
        Dense(512, activation="relu"),
        BatchNormalization(),
        Dropout(0.3),
        Dense(256, activation="relu"),
        BatchNormalization(),
        Dropout(0.3),
        Dense(128, activation="relu"),
        BatchNormalization(),
        Dense(128)
    ], name="Embedding")

    return model

print("Loading embedding model...")
write_log("Loading embedding model...")

embedding_model = get_embedding_model()
embedding_model.load_weights(str(MODEL_PATH))

print("Model loaded successfully.")
write_log("Model loaded successfully.")

# =========================================================
# HELPERS
# =========================================================

def l2_normalize(vector):
    return vector / np.linalg.norm(vector)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# =========================================================
# FACE DETECTION
# =========================================================

def extract_face(frame):
    try:
        detections = RetinaFace.detect_faces(frame)

        if not detections:
            return None

        largest_face = None
        largest_area = 0

        for key in detections:
            facial_area = detections[key]["facial_area"]
            x1, y1, x2, y2 = facial_area
            area = (x2 - x1) * (y2 - y1)
            if area > largest_area:
                largest_area = area
                largest_face = facial_area

        if largest_face is None:
            return None

        x1, y1, x2, y2 = largest_face
        padding = 20
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(frame.shape[1], x2 + padding)
        y2 = min(frame.shape[0], y2 + padding)

        face_crop = frame[y1:y2, x1:x2]
        return face_crop if face_crop.size > 0 else None

    except Exception as e:
        write_log(f"Face detection error: {str(e)}")
        return None

# =========================================================
# PREPROCESS & EMBED
# =========================================================

def preprocess_face(face_image):
    image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, (128, 128))
    image = image.astype("float32")
    image = np.expand_dims(image, axis=0)
    return preprocess_input(image)

def get_face_embedding(face_image):
    processed = preprocess_face(face_image)
    vector = embedding_model.predict(processed, verbose=0)[0]
    return l2_normalize(vector)

# =========================================================
# PRELOAD KNOWN FACES
# =========================================================

def load_upload_images():
    data = {}
    for booking_id, name in booking_index.items():
        folder = UPLOADS_DIR / booking_id
        if folder.exists():
            image_paths = [
                str(folder / f)
                for f in os.listdir(folder)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if image_paths:
                data[booking_id] = {"name": name, "paths": image_paths}
    return data

def preload_known_faces():
    print("Loading known faces...")
    write_log("Loading known faces...")

    uploads = load_upload_images()
    known_faces = {}

    for booking_id, data in uploads.items():
        embeddings = []

        for image_path in data["paths"]:
            image = cv2.imread(image_path)
            if image is None:
                continue

            face = extract_face(image)
            if face is None:
                msg = f"Skipping {image_path} (no face found)"
                print(msg)
                write_log(msg)
                continue

            try:
                emb = get_face_embedding(face)
                embeddings.append(emb)
            except Exception as e:
                msg = f"Error processing {image_path}: {str(e)}"
                print(msg)
                write_log(msg)

        if embeddings:
            known_faces[booking_id] = {
                "name": data["name"],
                "embeddings": embeddings   # store all, compare best per person
            }
            msg = f"Loaded: {data['name']} ({len(embeddings)} images)"
            print(f"  ✅ {msg}")
            write_log(msg)

    msg = f"Total known faces: {len(known_faces)}"
    print(f"✅ {msg}")
    write_log(msg)

    return known_faces

known_faces = preload_known_faces()

# =========================================================
# MAIN RECOGNITION FUNCTION
# =========================================================

SIMILARITY_THRESHOLD = 0.90

def process_identity_from_frame(frame):
    """
    Returns: {"name": str, "booking_id": str | None}
    """
    try:
        face = extract_face(frame)

        if face is None:
            write_log("No face detected -> Unknown")
            return {"name": "Unknown", "booking_id": None}

        current_embedding = get_face_embedding(face)

        scores = []

        for booking_id, data in known_faces.items():
            # Best-of-N cosine similarity against all stored embeddings
            best_score = max(
                cosine_similarity(stored, current_embedding)
                for stored in data["embeddings"]
            )
            write_log(f"{data['name']} ({booking_id}): {best_score:.6f}")
            scores.append((booking_id, data["name"], best_score))

        scores.sort(key=lambda x: x[2], reverse=True)

        best_booking_id, best_name, best_score = scores[0]
        second_best_score = scores[1][2] if len(scores) > 1 else 0.0
        score_gap = best_score - second_best_score

        write_log(
            f"Best: {best_name} ({best_score:.4f}) | "
            f"2nd: ({second_best_score:.4f}) | "
            f"Gap: {score_gap:.4f}"
        )

        if best_score > SIMILARITY_THRESHOLD:
            write_log(f"Final Match: {best_name} | booking_id: {best_booking_id}")
            return {"name": best_name, "booking_id": best_booking_id}

        write_log("Final Match: Unknown")
        return {"name": "Unknown", "booking_id": None}

    except Exception as e:
        write_log(f"Recognition error: {str(e)}")
        return {"name": "Unknown", "booking_id": None}