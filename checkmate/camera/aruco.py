"""Find the board corners from 4 ArUco markers, and measure how bright their black and white are."""

import cv2
import numpy as np

ARUCO_DICT = cv2.aruco.DICT_4X4_50

# Marker id placed just outside each board corner, in corners_px order.
ARUCO_IDS = {"a1": 0, "h1": 1, "h8": 2, "a8": 3}

MODULES = 6          # a 4x4 marker is 6 x 6 modules with its black border
MODULE_PX = 8        # pixels per module when a marker is straightened to measure it
MIN_CONTRAST = 50    # lightness between a marker's black and white, below which it isn't trusted


def _dictionary():
    return cv2.aruco.getPredefinedDictionary(ARUCO_DICT)


def marker_image(marker_id, size):
    """Grayscale image of one marker, size x size pixels, without a white border."""
    if hasattr(cv2.aruco, "generateImageMarker"):  # OpenCV >= 4.7
        return cv2.aruco.generateImageMarker(_dictionary(), marker_id, size)
    return cv2.aruco.drawMarker(_dictionary(), marker_id, size)  # OpenCV 4.6 from apt on Bookworm


def find_aruco_markers(frame):
    """The 4 corner markers in ARUCO_IDS order (a1, h1, h8, a8): each its 4 corners [x, y] as
    detected, starting at the marker's own top-left. Returns None if any marker is missing.
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
    return [found[i].tolist() for i in ARUCO_IDS.values()]


def board_corners(markers):
    """One board corner per marker, in the markers' order: of each marker, the corner closest to
    the middle of all 4. Which one is a1 is decided by calibrate_from_frame() from the pieces."""
    quads = [np.array(m, dtype=np.float32) for m in markers]
    center = np.mean([q.mean(axis=0) for q in quads], axis=0)
    result = []
    for pts in quads:
        nearest = pts[np.argmin(np.linalg.norm(pts - center, axis=1))]
        result.append([float(nearest[0]), float(nearest[1])])
    return result


def find_aruco_corners(frame):
    """The 4 board corners from the ArUco markers placed just outside them (see board_corners()).
    Returns None if any marker is missing.
    """
    markers = find_aruco_markers(frame)
    return None if markers is None else board_corners(markers)


def marker_levels(frame, markers):
    """(black, white): the lightness (LAB L, like the squares) of the markers' black and white
    modules in a BGR `frame`, at the places in `markers` (from find_aruco_markers()).

    A marker whose modules don't match its own pattern (a hand over it, glare, out of the
    picture) is skipped. Returns None if no marker is clear.
    """
    side = MODULES * MODULE_PX
    square = np.float32([[0, 0], [side, 0], [side, side], [0, side]])
    blacks, whites = [], []
    for marker_id, quad in zip(ARUCO_IDS.values(), markers):
        matrix = cv2.getPerspectiveTransform(np.float32(quad), square)
        patch = cv2.warpPerspective(frame, matrix, (side, side))
        lightness = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)[:, :, 0].astype(np.float32)
        # The middle of each module, away from its blurry edges.
        modules = lightness.reshape(MODULES, MODULE_PX, MODULES, MODULE_PX)[:, 2:-2, :, 2:-2].mean(axis=(1, 3))
        white = marker_image(marker_id, MODULES) > 127
        black_level, white_level = float(np.median(modules[~white])), float(np.median(modules[white]))
        middle = (black_level + white_level) / 2
        if (white_level - black_level >= MIN_CONTRAST
                and modules[white].min() > middle > modules[~white].max()):
            blacks.append(black_level)
            whites.append(white_level)
    if not blacks:
        return None
    return float(np.median(blacks)), float(np.median(whites))
