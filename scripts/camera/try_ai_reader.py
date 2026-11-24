"""Send one photo of the board to the vision model and print what it read (camera.classifier "ai").

Needs DEEPSEEK_API_KEY. Each run is one paid request (a retry or two if the answer is unusable).

The board's corners come from the calibration file if it matches the photo's size (a photo
from the same camera that was calibrated), else from the 4 ArUco markers in the photo: then the
pieces must be in the starting position to tell where a1 is, or the markers must be in their
standard corners (0 at a1, 1 at h1, 2 at h8, 3 at a8).

Usage: python scripts/camera/try_ai_reader.py PHOTO [CALIBRATION_FILE]
       writes PHOTO_ai.jpg next to the photo: the picture the model was sent
"""

import json
import os
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from checkmate.camera.ai_reader import DeepSeekReader, annotate  # noqa: E402
from checkmate.camera.aruco import board_corners, find_aruco_markers  # noqa: E402
from checkmate.camera.vision import calibrate_from_frame  # noqa: E402
from checkmate.config import DEFAULT_PATH, REPO_ROOT, load_config  # noqa: E402


def board_corners_in(photo, calibration_file):
    h, w = photo.shape[:2]
    if calibration_file.exists():
        calib = json.loads(calibration_file.read_text())
        if calib.get("frame_size") == [w, h]:
            return calib["corners_px"], f"from {calibration_file.name}"
    markers = find_aruco_markers(photo)
    if markers is None:
        sys.exit("no calibration file for this photo size, and the 4 ArUco markers aren't all visible")
    calib = calibrate_from_frame(photo, board_corners(markers), markers)
    if calib is not None:
        return calib["corners_px"], "from the markers; a1 from the starting position"
    return board_corners(markers), "from the markers in their standard corners (not a starting position)"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    photo_path = Path(sys.argv[1])
    photo = cv2.imread(str(photo_path))
    if photo is None:
        sys.exit(f"can't read {photo_path}")
    config = load_config(os.environ.get("CHECKMATE_CONFIG", DEFAULT_PATH))["camera"]
    calibration = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO_ROOT / config.get("calibration_file", "calibration.json")

    corners, where = board_corners_in(photo, calibration)
    jpeg = annotate(photo, corners)
    sent = photo_path.with_name(photo_path.stem + "_ai.jpg")
    sent.write_bytes(jpeg)
    print(f"board corners {where}; picture sent: {sent}")

    reader = DeepSeekReader(config.get("ai") or {})
    start = time.monotonic()
    res = reader.read(jpeg)
    print(f"{time.monotonic() - start:.1f} s")
    if not res["ok"]:
        sys.exit(f"{res['error']}: {res['message']}")
    occ = res["occupancy"]
    print("obstructed" if res["obstructed"] else "board clear")
    for rank in range(7, -1, -1):
        print(f"{rank + 1}  {' '.join(occ[rank * 8:rank * 8 + 8])}")
    print("   a b c d e f g h")


if __name__ == "__main__":
    main()
