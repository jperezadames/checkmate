"""HTTP routes under /api (contracts/interfaces.md section 5.1).

Route handlers never call the modules: they read the last messages from the game loop, or
hand work to it through the hub.
"""

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from checkmate.errors import err

router = APIRouter(prefix="/api")

STARTING = err("NOT_STARTED", "the game loop is still starting")


def _latest(msg):
    return msg if msg is not None else JSONResponse(STARTING, status_code=503)


@router.get("/info")
def info(request: Request):
    return _latest(request.app.state.hub.info)


@router.get("/state")
def state(request: Request):
    return _latest(request.app.state.hub.state)


@router.post("/command")
async def command(request: Request):
    try:
        cmd = json.loads(await request.body())
    except ValueError:
        return JSONResponse(err("BAD_REQUEST", "the body must be JSON"), status_code=400)
    problem = request.app.state.hub.submit(cmd)
    if problem:
        return JSONResponse(problem, status_code=400)
    return {"ok": True}


@router.get("/camera.jpg")
def camera_jpg(request: Request):
    # A plain def runs in a worker thread, so waiting for the loop doesn't block the server.
    image = request.app.state.hub.debug_image()
    if image is None:
        return Response(status_code=404)
    return Response(image, media_type="image/jpeg")


def _jpeg(request, kind):
    image = request.app.state.hub.debug_image(kind)
    if image is None:
        return Response(status_code=404)
    return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/frame.jpg")
def frame_jpg(request: Request):
    """The latest camera frame as it is."""
    return _jpeg(request, "frame")


@router.get("/ai.jpg")
def ai_jpg(request: Request, sent: bool = False):
    """The picture the vision model gets from the current frame (section 2.8); ?sent=1: the last
    one actually sent with camera.classifier "ai"."""
    return _jpeg(request, "ai_sent" if sent else "ai")


LIVE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CheckMate camera</title>
<style>
  body { margin: 16px; font: 14px system-ui, sans-serif; background: #111; color: #ddd; }
  .row { display: flex; flex-wrap: wrap; gap: 16px; }
  figure { margin: 0; flex: 1 1 400px; }
  img { width: 100%; background: #222; min-height: 120px; }
  figcaption { margin: 4px 0; color: #999; }
</style></head>
<body>
<p>Refreshes every <span id="ms"></span> ms (<code>?ms=</code> to change). <span id="status"></span></p>
<div class="row">
  <figure><figcaption>Camera (/api/frame.jpg)</figcaption><img id="frame" alt="no frame yet"></figure>
  <figure><figcaption>What the AI sees, from this frame (/api/ai.jpg); needs a calibration</figcaption>
    <img id="ai" alt="not calibrated"></figure>
  <figure id="sent-box" hidden><figcaption>Last picture sent to the AI (/api/ai.jpg?sent=1)</figcaption>
    <img id="sent" alt=""></figure>
</div>
<script>
const ms = Math.max(100, Number(new URLSearchParams(location.search).get("ms")) || 500);
document.getElementById("ms").textContent = ms;
// Load the next picture off-screen and swap it in, so the page doesn't flicker.
function refresh(id, url, box) {
  const next = new Image();
  next.onload = () => { document.getElementById(id).src = next.src; if (box) document.getElementById(box).hidden = false; };
  next.onerror = () => { if (box) document.getElementById(box).hidden = true; };
  next.src = url + (url.includes("?") ? "&" : "?") + "t=" + Date.now();
}
function tick() {
  refresh("frame", "frame.jpg");
  refresh("ai", "ai.jpg");
  refresh("sent", "ai.jpg?sent=1", "sent-box");
  document.getElementById("status").textContent = new Date().toLocaleTimeString();
}
tick();
setInterval(tick, ms);
</script>
</body></html>
"""


@router.get("/live")
def live():
    """A page showing the camera frame and the picture the AI gets, refreshed every 0.5 s."""
    return HTMLResponse(LIVE_PAGE)


@router.get("/health")
def health(request: Request):
    state = request.app.state.hub.state
    devices = state["devices"] if state else {"camera": "error", "engine": "error", "led": "error"}
    return {"ok": True, "devices": devices}
