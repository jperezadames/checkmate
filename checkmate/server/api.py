"""HTTP routes under /api (contracts/interfaces.md section 5.1)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    # TODO: report real device status once the modules are wired in.
    return {"ok": True, "devices": {"camera": "unknown", "engine": "unknown", "led": "unknown"}}


# TODO: GET /info, GET /state, POST /command, GET /camera.jpg
