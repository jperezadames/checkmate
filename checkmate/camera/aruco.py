"""Find the board corners from 4 ArUco markers."""

import cv2
import numpy as np

# Marker ids placed next to the a1, h1, h8, a8 board corners.
ARUCO_IDS = (0, 1, 2, 3)


def _aruco_dictionary(name):
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def find_aruco_corners(frame, dict_name="DICT_4X4_50"):
    """Board corners [a1, h1, h8, a8] from 4 ArUco markers (ids 0-3) placed just outside each
    board corner. For each marker, the corner closest to the middle of all 4 markers is used.
    Returns None if any marker is missing.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    dictionary = _aruco_dictionary(dict_name)
    if hasattr(cv2.aruco, "ArucoDetector"):  # OpenCV >= 4.7
        detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
        marker_corners, ids, _ = detector.detectMarkers(gray)
    else:  # OpenCV 4.6 from apt on Bookworm
        params = cv2.aruco.DetectorParameters_create()
        marker_corners, ids, _ = cv2.aruco.detectMarkers(gray, dictionary, parameters=params)
    if ids is None:
        return None

    found = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), marker_corners)}
    if not all(i in found for i in ARUCO_IDS):
        return None
    center = np.mean([found[i].mean(axis=0) for i in ARUCO_IDS], axis=0)
    result = []
    for i in ARUCO_IDS:
        pts = found[i]
        nearest = pts[np.argmin(np.linalg.norm(pts - center, axis=1))]
        result.append([float(nearest[0]), float(nearest[1])])
    return result
