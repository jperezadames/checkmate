"""Camera + move detection (owner: Harry). Contract: contracts/interfaces.md section 2.

Public API:
    occupancy_from_fen(fen) -> str
    detect_move(fen, occupancy) -> dict
    Camera(config)      real camera (Picamera2 or V4L2 webcam)
    FakeCamera(config)  same methods, no hardware (section 2.7)

Everything returned to main is a plain dict / list / str (section 0.2). Public
methods never raise; they return {"ok": False, "error": CODE, "message": ...}.
"""

from checkmate.camera.camera import Camera
from checkmate.camera.fake import FakeCamera
from checkmate.camera.move_detection import detect_move
from checkmate.camera.occupancy import START_FEN, occupancy_from_fen

__all__ = ["START_FEN", "Camera", "FakeCamera", "detect_move", "occupancy_from_fen"]
