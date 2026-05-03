import cv2
import dlib
import numpy as np
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

FACE_ENCODER_PATH = BASE_DIR / "models" / "dlib_face_recognition_resnet_model_v1.dat"
SHAPE_PREDICTOR_PATH = BASE_DIR / "models" / "shape_predictor_68_face_landmarks.dat"
UPLOADS_DIR = BASE_DIR / "services" / "api" / "uploads"
BOOKING_INDEX_PATH = BASE_DIR / "booking_index.json"

face_detector = dlib.get_frontal_face_detector() #type: ignore
face_encoder = dlib.face_recognition_model_v1(str(FACE_ENCODER_PATH)) #type: ignore
shape_predictor = dlib.shape_predictor(str(SHAPE_PREDICTOR_PATH)) #type: ignore

with open(BOOKING_INDEX_PATH, "r") as f:
    booking_index = json.load(f)

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
                data[booking_id] = {
                    "name": name,
                    "paths": image_paths
                }
    return data

def get_face_descriptor(image_paths):
    descriptors = []
    for path in image_paths:
        img = cv2.imread(path)
        if img is None:
            continue
        faces = face_detector(img, 1)
        if faces:
            shape = shape_predictor(img, faces[0])
            descriptor = np.array(face_encoder.compute_face_descriptor(img, shape))
            descriptors.append(descriptor)
    return np.mean(descriptors, axis=0) if descriptors else None

def preload_known_faces():
    print("Loading known faces...")
    uploads = load_upload_images()
    known_faces = {}

    for booking_id, data in uploads.items():
        desc = get_face_descriptor(data["paths"])
        if desc is not None:
            known_faces[booking_id] = {
                "name": data["name"],
                "embedding": desc
            }
            print(f"  ✅ Loaded {data['name']}")
    print(f"✅ Total known faces: {len(known_faces)}")
    return known_faces

known_faces = preload_known_faces()

def process_identity_from_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_detector(gray, 1)

    best_match = {"name": "Unknown", "booking_id": None}
    min_distance = 0.4

    for face in faces:
        x, y, w, h = face.left(), face.top(), face.width(), face.height()
        shape = shape_predictor(frame, dlib.rectangle(x, y, x + w, y + h)) #type: ignore
        descriptor = np.array(face_encoder.compute_face_descriptor(frame, shape))

        for booking_id, data in known_faces.items():
            distance = np.linalg.norm(data["embedding"] - descriptor)
            if distance < min_distance:
                min_distance = distance
                best_match = {
                    "name": data["name"],
                    "booking_id": booking_id
                }

    return best_match