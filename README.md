# Smart Hotel Lock System

A real-time smart hotel system combining face recognition, QR-based check-in, and hardware-ready access control.

---

## 🌐 UI Preview

👉 https://checkin.ishanx.tech  

> This is **only a UI preview**.  
> The full system is designed for **local deployment**, as it requires:
> - Camera access  
> - MQ server
> - Low-latency local processing  

---

## ⚙️ Features

- Face recognition-based identity detection  
- QR-based secure check-in (HS256 + signature)  
- Real-time camera streaming via WebRTC/ZMQ  
- Event-driven architecture (ZMQ pipeline)  
- Smart lock interface with visual + audio feedback  
- Modular microservices-based design  

---

## 🏗️ Architecture
<img width="1920" height="1080" alt="SYSTEM ARCHITECTURE AND FLOW" src="https://github.com/user-attachments/assets/30eff8a6-219f-4fb9-87f2-955bd91f80b0" />
---

## 🚀 Setup

### 1. Install `uv`
---

### 2. Install dependencies

```bash
uv sync
```

---

### 3. Add required models

Place trained models inside:

```
models/
```

> These are **not included** because GitHub does not allow large files.

---

### 4. Environment variables

Create `.env`:

```env
MONGODB_URL=...
SMTP_USERNAME=...
SMTP_PASSWORD=...
CHECKIN_SECRET=...
```

---

## ▶️ Run Services

Run each service in separate terminals:

```bash
uv run services/camera/serve_camera.py
```

```bash
python3 -m http.server 5500 -d services/ui
```

```bash
uv run services/stream_receiver/camera_recv.py
```

```bash
uv run python -m services.face_recognition.cv
```

```bash
uv run services/bridge/zmq_ws_bridge.py
```

```bash
uv run uvicorn services.api.app.main:app --reload --app-dir .
```

---

## 🧠 Tech Stack

* Python (FastAPI, OpenCV, dlib)
* ZMQ (event-driven communication)
* WebRTC (camera streaming)
* MongoDB
  
---
## Smart Lock System
<img width="1280" height="762" alt="image" src="https://github.com/user-attachments/assets/c49fec4c-b509-4c80-9733-5990f657122b" />

