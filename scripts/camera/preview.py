"""Live camera check: shows the (warped) board and prints the occupancy.

Usage: python scripts/camera/preview.py [config.json]
Keys: c = calibrate (board in the starting position), q = quit.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from checkmate.camera import Camera  # noqa: E402
from checkmate.config import DEFAULT_PATH, load_config  # noqa: E402

config = load_config(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
cam = Camera(config["camera"])
print("start:", cam.start())

last_occupancy = None
try:
    while True:
        jpg = cam.get_debug_image()
        if jpg is not None:
            cv2.imshow("checkmate camera", cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR))

        obs = cam.get_observation()
        if obs["ok"] and obs["stable"] and obs["occupancy"] != last_occupancy:
            last_occupancy = obs["occupancy"]
            rows = [obs["occupancy"][r * 8:(r + 1) * 8] for r in range(7, -1, -1)]
            print("\n".join(rows), "low:", obs["low_confidence"], "\n")

        key = cv2.waitKey(100) & 0xFF
        if key == ord("q"):
            break
        if key == ord("c"):
            print("calibrate:", cam.calibrate())
finally:
    cam.close()
    cv2.destroyAllWindows()
