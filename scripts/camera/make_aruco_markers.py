"""Generate the 4 ArUco markers used for camera calibration.

Print them and place each one just outside a board corner, touching it:
    id 0 -> a1 corner, id 1 -> h1 corner, id 2 -> h8 corner, id 3 -> a8 corner

Usage: python scripts/camera/make_aruco_markers.py [out_dir] [size_px]
"""

import sys
from pathlib import Path

import cv2

out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "markers")
size = int(sys.argv[2]) if len(sys.argv) > 2 else 400
out_dir.mkdir(parents=True, exist_ok=True)

dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
for marker_id, corner in zip(range(4), ["a1", "h1", "h8", "a8"]):
    if hasattr(cv2.aruco, "generateImageMarker"):  # OpenCV >= 4.7
        img = cv2.aruco.generateImageMarker(dictionary, marker_id, size)
    else:
        img = cv2.aruco.drawMarker(dictionary, marker_id, size)
    # White border so the marker can be detected when printed.
    img = cv2.copyMakeBorder(img, size // 8, size // 8, size // 8, size // 8, cv2.BORDER_CONSTANT, value=255)
    path = out_dir / f"aruco_{marker_id}_{corner}.png"
    cv2.imwrite(str(path), img)
    print(path)
