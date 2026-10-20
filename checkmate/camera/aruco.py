"""Find the board corners from 4 ArUco markers."""

import cv2
import numpy as np

ARUCO_DICT = cv2.aruco.DICT_4X4_50

# Marker id placed just outside each board corner, in corners_px order.
ARUCO_IDS = {"a1": 0, "h1": 1, "h8": 2, "a8": 3}


def _dictionary():
    return cv2.aruco.getPredefinedDictionary(ARUCO_DICT)


def marker_image(marker_id, size):
    """Grayscale image of one marker, size x size pixels, without a white border."""
    if hasattr(cv2.aruco, "generateImageMarker"):  # OpenCV >= 4.7
        return cv2.aruco.generateImageMarker(_dictionary(), marker_id, size)
    return cv2.aruco.drawMarker(_dictionary(), marker_id, size)  # OpenCV 4.6 from apt on Bookworm


def find_aruco_corners(frame):
    """Board corners [a1, h1, h8, a8] from the 4 ArUco markers placed just outside each board
    corner. For each marker, the corner closest to the middle of all 4 markers is used.
    Returns None if any marker is missing.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    if hasattr(cv2.aruco, "ArucoDetector"):  # OpenCV >= 4.7
        detector = cv2.aruco.ArucoDetector(_dictionary(), cv2.aruco.DetectorParameters())
        marker_corners, ids, _ = detector.detectMarkers(gray)
    else:  # OpenCV 4.6 from apt on Bookworm
        params = cv2.aruco.DetectorParameters_create()
        marker_corners, ids, _ = cv2.aruco.detectMarkers(gray, _dictionary(), parameters=params)
    if ids is None:
        return None

    found = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), marker_corners)}
    if not all(i in found for i in ARUCO_IDS.values()):
        return None
    center = np.mean([found[i].mean(axis=0) for i in ARUCO_IDS.values()], axis=0)
    result = []
    for i in ARUCO_IDS.values():
        pts = found[i]
        nearest = pts[np.argmin(np.linalg.norm(pts - center, axis=1))]
        result.append([float(nearest[0]), float(nearest[1])])
    return result
