"""Motion check behind get_observation()["stable"] (contracts/interfaces.md section 2.3)."""

import cv2
import numpy as np

# The warped board is shrunk to SMALL x SMALL pixels before comparing: 8 x 8 pixels per square.
SMALL = 64

# Mean absolute grayscale difference (0-255) inside one square between two frames that counts as
# motion. Checked per square, so a hand over a few squares isn't averaged away by the rest.
MOTION_THRESHOLD = 10.0


def max_square_diff(a, b):
    """Largest per-square mean absolute difference between two SMALL x SMALL images."""
    per_square = np.abs(a - b).reshape(8, SMALL // 8, 8, SMALL // 8).mean(axis=(1, 3))
    return float(per_square.max())


class MotionDetector:
    def __init__(self, stable_time_s):
        self.stable_time_s = stable_time_s
        self._prev_gray = None
        self._last_motion = 0.0

    def reset(self):
        """Forget the previous frame, e.g. after recalibrating; the next frame counts as motion."""
        self._prev_gray = None

    def update(self, warped, ts) -> bool:
        """Feed the next warped board; True if no square has changed for stable_time_s."""
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (SMALL, SMALL), interpolation=cv2.INTER_AREA).astype(np.float32)
        if self._prev_gray is None or max_square_diff(gray, self._prev_gray) > MOTION_THRESHOLD:
            self._last_motion = ts
        self._prev_gray = gray
        return ts - self._last_motion >= self.stable_time_s
