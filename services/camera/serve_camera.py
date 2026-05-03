import asyncio
import json
import cv2
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
import aiohttp_cors
from av import VideoFrame
import threading


class SharedCamera:
    def __init__(self, camera_index=0, width=1280, height=720):
        self.camera_index = camera_index
        self.width = width
        self.height = height

        self.cap = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.frame_ready = threading.Event()
        self.running = False
        self.thread = None

        self._open()

    def _open(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise Exception(f"Could not open camera {self.camera_index}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        aw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Camera {self.camera_index}: requested {self.width}x{self.height}, got {aw}x{ah}")

        self.running = True
        self.frame_ready.clear()
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

        if not self.frame_ready.wait(timeout=5.0):
            self.running = False
            raise Exception(f"Camera {self.camera_index} failed to produce first frame within 5s")

        print(f"Camera {self.camera_index} ready")

    def _reader(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print(f"Camera {self.camera_index} read failed")
                self.running = False
                break
            with self.frame_lock:
                self.latest_frame = frame
                if not self.frame_ready.is_set():
                    self.frame_ready.set()

    def get_frame(self):
        with self.frame_lock:
            return self.latest_frame

    def get_dimensions(self):
        if self.cap and self.cap.isOpened():
            return int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return self.width, self.height

    def release(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)


class WebcamTrack(VideoStreamTrack):
    def __init__(self, shared_camera: SharedCamera):
        super().__init__()
        self.camera = shared_camera
        self.camera_name = f"Camera Index {shared_camera.camera_index}"

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame = self.camera.get_frame()

        if frame is None:
            w, h = self.camera.get_dimensions()
            frame = np.zeros((h, w, 3), dtype=np.uint8)

        frame_av = VideoFrame.from_ndarray(frame, format="bgr24")
        frame_av.pts = pts
        frame_av.time_base = time_base
        return frame_av

    def stop(self):
        pass


shared_camera: SharedCamera | None = None
pcs: set[RTCPeerConnection] = set()


async def cleanup_pc(pc: RTCPeerConnection):
    pcs.discard(pc)
    if pc.signalingState != "closed":
        await pc.close()


async def offer(request):
    params = await request.json()

    sdp = params.get("sdp")
    type_ = params.get("type")
    if not sdp or not type_:
        return web.Response(status=400, text="Missing sdp or type")

    offer_desc = RTCSessionDescription(sdp=sdp, type=type_)

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        state = pc.iceConnectionState
        print(f"ICE state: {state}")
        if state in ("failed", "closed", "disconnected"):
            await cleanup_pc(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        state = pc.connectionState
        print(f"Connection state: {state}")
        if state in ("failed", "closed"):
            await cleanup_pc(pc)

    try:
        track = WebcamTrack(shared_camera)
        pc.addTrack(track)
        print(f"Added {track.camera_name} to peer connection")
    except Exception as e:
        print(f"Failed to attach camera track: {e}")
        await cleanup_pc(pc)
        return web.Response(status=500, text=str(e))

    try:
        await pc.setRemoteDescription(offer_desc)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
    except Exception as e:
        print(f"SDP negotiation failed: {e}")
        await cleanup_pc(pc)
        return web.Response(status=500, text=str(e))

    return web.Response(
        content_type="application/json",
        text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
    )


async def on_shutdown(app):
    print("Shutting down, closing all peer connections...")
    coros = [cleanup_pc(pc) for pc in list(pcs)]
    await asyncio.gather(*coros, return_exceptions=True)
    pcs.clear()
    if shared_camera is not None:
        shared_camera.release()


def handle_async_exception(loop, context):
    exception = context.get("exception")
    if isinstance(exception, asyncio.InvalidStateError):
        return
    msg = context.get("message", "unknown")
    print(f"Unhandled async exception: {msg}")
    if exception:
        print(f"  {type(exception).__name__}: {exception}")


async def main():
    global shared_camera
    shared_camera = SharedCamera(camera_index=0)

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_post("/offer", offer)

    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    for route in list(app.router.routes()):
        cors.add(route)

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(handle_async_exception)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 9000)
    await site.start()

    print("Running on http://0.0.0.0:9000")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping server...")