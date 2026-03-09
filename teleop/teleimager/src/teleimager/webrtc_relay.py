import asyncio
import ssl
import os
import numpy as np
from pathlib import Path
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import argparse

from .image_client import ImageClient


class ZmqToWebrtcTrack(VideoStreamTrack):
    """ZMQ로 수신한 BGR 이미지를 WebRTC 비디오 스트림으로 변환하는 트랙"""
    kind = "video"

    def __init__(self, get_frame_fn):
        super().__init__()
        self.get_frame_fn = get_frame_fn
        self.blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        tele_img = self.get_frame_fn()
        img_bgr = tele_img.bgr if tele_img is not None else None

        if img_bgr is None:
            img_bgr = self.blank_frame
            await asyncio.sleep(0.01)

        frame = VideoFrame.from_ndarray(img_bgr, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame


@web.middleware
async def cors_middleware(request, handler):
    """Quest 브라우저에서 WebRTC offer를 보낼 때 CORS가 필요"""
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


async def _handle_offer(request, get_frame_fn):
    """공통 WebRTC offer 처리 로직"""
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    request.app['pcs'].add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "closed"):
            await pc.close()
            request.app['pcs'].discard(pc)

    pc.addTrack(ZmqToWebrtcTrack(get_frame_fn))

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })


async def offer_head(request):
    """Head camera WebRTC offer endpoint"""
    return await _handle_offer(request, request.app['image_client'].get_head_frame)


async def offer_left_wrist(request):
    """Left wrist camera WebRTC offer endpoint"""
    return await _handle_offer(request, request.app['image_client'].get_left_wrist_frame)


async def offer_right_wrist(request):
    """Right wrist camera WebRTC offer endpoint"""
    return await _handle_offer(request, request.app['image_client'].get_right_wrist_frame)


def resolve_ssl_context(cert_file=None, key_file=None):
    """Resolve SSL certificates (same priority as televuer):
    1. Explicit cert_file/key_file args
    2. XR_TELEOP_CERT / XR_TELEOP_KEY env vars
    3. ~/.config/xr_teleoperate/cert.pem & key.pem
    """
    env_cert = os.getenv("XR_TELEOP_CERT")
    env_key = os.getenv("XR_TELEOP_KEY")

    if cert_file is None or key_file is None:
        if env_cert and env_key:
            cert_file = cert_file or env_cert
            key_file = key_file or env_key
        else:
            user_conf_dir = Path.home() / ".config" / "xr_teleoperate"
            cert_path = user_conf_dir / "cert.pem"
            key_path = user_conf_dir / "key.pem"
            if cert_path.exists() and key_path.exists():
                cert_file = cert_file or str(cert_path)
                key_file = key_file or str(key_path)

    if cert_file and key_file:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        return ssl_context

    print("[WebRTC Relay] Warning: No SSL certificates found. Quest requires HTTPS for WebRTC.")
    return None


async def on_shutdown(app):
    """Clean up all peer connections and image client"""
    coros = [pc.close() for pc in app['pcs']]
    await asyncio.gather(*coros)
    app['pcs'].clear()
    app['image_client'].close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC relay server for ZMQ camera images")
    parser.add_argument('--host', type=str, default='10.86.160.1', help='Robot ZMQ server IP')
    parser.add_argument('--port', type=int, default=8080, help='WebRTC relay server port')
    args = parser.parse_args()

    print(f"[WebRTC Relay] Connecting to ZMQ server at {args.host}...")
    client = ImageClient(host=args.host, request_bgr=True)

    app = web.Application(middlewares=[cors_middleware])
    app['image_client'] = client
    app['pcs'] = set()
    app.router.add_post("/offer", offer_head)
    app.router.add_post("/offer/left_wrist", offer_left_wrist)
    app.router.add_post("/offer/right_wrist", offer_right_wrist)
    app.on_shutdown.append(on_shutdown)

    ssl_context = resolve_ssl_context()

    protocol = "https" if ssl_context else "http"
    print(f"[WebRTC Relay] Server starting at {protocol}://0.0.0.0:{args.port}")
    print(f"  Head camera:        /offer")
    print(f"  Left wrist camera:  /offer/left_wrist")
    print(f"  Right wrist camera: /offer/right_wrist")
    web.run_app(app, host="0.0.0.0", port=args.port, ssl_context=ssl_context)
