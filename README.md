uv run services/camera/serve_camera.py
python3 -m http.server 5500 -d services/ui
uv run services/stream_receiver/camera_recv.py
uv run python -m services.face_recognition.cv
uv run services/bridge/zmq_ws_bridge.py
uv run uvicorn services.api.app.main:app --reload --app-dir .