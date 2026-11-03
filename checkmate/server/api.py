"""HTTP routes under /api (contracts/interfaces.md section 5.1).

Route handlers never call the modules: they read the last messages from the game loop, or
hand work to it through the hub.
"""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

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


@router.get("/health")
def health(request: Request):
    state = request.app.state.hub.state
    devices = state["devices"] if state else {"camera": "error", "engine": "error", "led": "error"}
    return {"ok": True, "devices": devices}
