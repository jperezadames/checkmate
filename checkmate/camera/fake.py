"""FakeCamera (contracts/interfaces.md section 2.7): same methods as Camera, no hardware."""

import time

from checkmate.camera.occupancy import START_FEN, occupancy_from_fen
from checkmate.errors import err


class FakeCamera:
    """Tests set `occupancy` and `stable` directly; get_observation() returns them."""

    def __init__(self, config: dict = None):
        self.occupancy = occupancy_from_fen(START_FEN)
        self.stable = True
        self.low_confidence = []
        self.started = False
        self._seq = 0

    def start(self) -> dict:
        self.started = True
        return {"ok": True, "calibrated": True}

    def calibrate(self) -> dict:
        return {
            "ok": True,
            "corners_px": [[0, 720], [1280, 720], [1280, 0], [0, 0]],
            "frame_size": [1280, 720],
            "occupancy": self.occupancy,
        }

    def get_observation(self) -> dict:
        if not self.started:
            return err("CAMERA_NOT_READY", "camera not started")
        self._seq += 1
        return {
            "ok": True,
            "ts": time.monotonic(),
            "seq": self._seq,
            "stable": self.stable,
            "occupancy": self.occupancy,
            "low_confidence": list(self.low_confidence),
        }

    def get_debug_image(self):
        return None

    def close(self) -> None:
        self.started = False
