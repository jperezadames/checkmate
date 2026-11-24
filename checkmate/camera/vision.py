"""Board image processing: warp, per-square features, classification, calibration fit.

Pure functions on numpy images, so they can be tested with synthetic pictures.
"""

import chess
import cv2
import numpy as np

from checkmate.camera.aruco import MIN_CONTRAST, marker_levels
from checkmate.camera.occupancy import START_FEN, occupancy_from_fen

# Top-down board image: WARP_SIZE x WARP_SIZE pixels, a8 at top-left, h1 at bottom-right.
WARP_SIZE = 640
CELL = WARP_SIZE // 8

# Fraction of each square (centered) used for classification; edges are noisy.
PATCH_FRACTION = 0.5

# A square is "low confidence" if (nearest distance / second nearest distance) is above this.
LOW_CONFIDENCE_RATIO = 0.7

# Classes are the occupancy characters (section 1.2).
CLASSES = (".", "W", "B")

# What the board must show while calibrating.
START_OCC = occupancy_from_fen(START_FEN)


def square_rect(i):
    """Pixel rect (x0, y0, x1, y1) of square index i in the warped image."""
    file, rank = i % 8, i // 8
    x0, y0 = file * CELL, (7 - rank) * CELL
    return x0, y0, x0 + CELL, y0 + CELL


def is_dark_square(i):
    # a1 (file 0, rank 0) is dark.
    return (i % 8 + i // 8) % 2 == 0


def _shade(i):
    return "dark" if is_dark_square(i) else "light"


def warp_board(frame, corners_px):
    """Perspective-warp `frame` to a top-down board. corners_px order: a1, h1, h8, a8."""
    src = np.array(corners_px, dtype=np.float32)
    dst = np.array([[0, WARP_SIZE], [WARP_SIZE, WARP_SIZE], [WARP_SIZE, 0], [0, 0]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(frame, matrix, (WARP_SIZE, WARP_SIZE))


def square_features(warped):
    """64 x 2 array: (mean, std) of the L channel in the center patch of each square."""
    lightness = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)[:, :, 0].astype(np.float32)
    margin = int(CELL * (1 - PATCH_FRACTION) / 2)
    feats = np.zeros((64, 2), dtype=np.float32)
    for i in range(64):
        x0, y0, x1, y1 = square_rect(i)
        patch = lightness[y0 + margin:y1 - margin, x0 + margin:x1 - margin]
        feats[i] = (patch.mean(), patch.std())
    return feats


def fit_centroids(feats):
    """Class centroids from a board in the starting position, separately for light and dark squares."""
    centroids = {}
    for shade in ("dark", "light"):
        centroids[shade] = {}
        for cls in CLASSES:
            idx = [i for i in range(64) if _shade(i) == shade and START_OCC[i] == cls]
            centroids[shade][cls] = feats[idx].mean(axis=0).tolist()
    return centroids


def classify(feats, centroids):
    """Nearest-centroid classification -> (occupancy string, list of low-confidence squares)."""
    chars, low_confidence = [], []
    for i in range(64):
        cents = centroids[_shade(i)]
        dists = sorted((float(np.linalg.norm(feats[i] - np.array(cents[c]))), c) for c in CLASSES)
        chars.append(dists[0][1])
        if dists[1][0] > 0 and dists[0][0] / dists[1][0] > LOW_CONFIDENCE_RATIO:
            low_confidence.append(chess.square_name(i))
    return "".join(chars), low_confidence


def match_lighting(feats, frame, calib):
    """Square features as if lit like the calibration frame.

    The markers' black and white in `frame` are mapped onto their lightness at calibration, and
    every square with them (a straight line through both), so the whole picture getting brighter
    or darker (room light, a screen's brightness) doesn't change the classes. A change in one
    place only (a shadow, a lit LED) isn't corrected. Unchanged when the calibration has no
    markers (manual corners) or no marker is clear in `frame`.
    """
    if calib["levels"] is None:
        return feats
    now = marker_levels(frame, calib["markers_px"])
    if now is None or now[1] - now[0] < MIN_CONTRAST:
        return feats
    (black0, white0), (black, white) = calib["levels"], now
    gain = (white0 - black0) / (white - black)
    matched = feats.copy()
    matched[:, 0] = black0 + (feats[:, 0] - black) * gain  # mean
    matched[:, 1] = feats[:, 1] * gain                       # spread
    return matched


def _orientation_ok(feats):
    """Quick checks that the warped board could be the starting position the right way round.

    - empty dark squares must be darker than empty light squares (catches 90° turns and the
      mirror images that swap the square colors)
    - ranks 1-2 (white pieces) must be brighter than ranks 7-8 (catches 180° turns)
    Mirror images along a diagonal pass both; calibrate_from_frame() rules them out.
    """
    empty = [i for i in range(64) if START_OCC[i] == "."]
    dark = np.mean([feats[i, 0] for i in empty if is_dark_square(i)])
    light = np.mean([feats[i, 0] for i in empty if not is_dark_square(i)])
    white = np.mean([feats[i, 0] for i in range(64) if START_OCC[i] == "W"])
    black = np.mean([feats[i, 0] for i in range(64) if START_OCC[i] == "B"])
    return dark < light and white > black


def _scatter(feats, centroids):
    """How far the squares are from their starting-position class centroids (lower = better fit)."""
    return sum(float(np.sum((feats[i] - centroids[_shade(i)][START_OCC[i]]) ** 2)) for i in range(64))


def _around_the_board(corners):
    """The 4 corners in order around their middle, so any marker can sit in any corner."""
    cx, cy = np.mean(corners, axis=0)
    return sorted(corners, key=lambda p: np.arctan2(p[1] - cy, p[0] - cx))


def _corner_orders(corners):
    """The 8 ways to read 4 corners as a1, h1, h8, a8: each rotation, as given and mirrored."""
    mirrored = [corners[0], corners[3], corners[2], corners[1]]
    for order in (corners, mirrored):
        for shift in range(4):
            yield order[shift:] + order[:shift]


def calibrate_from_frame(frame, corners_px, markers_px=None):
    """Fit a calibration from one frame of the board in the starting position.

    `markers_px` (from find_aruco_markers(), None with manual corners) is kept with their black
    and white lightness now, for match_lighting() on later frames.

    `corners_px` may come in any order. Tries the 8 ways they can map to a1, h1, h8, a8 going
    around the board. Among those that pass
    _orientation_ok(), keeps the one whose squares fit their starting-position class best: a board
    mirrored along a diagonal mixes pieces and empty squares in every class, so it fits badly.
    Returns a calibration dict, or None if no order fits.
    """
    corners = _around_the_board([list(map(float, c)) for c in corners_px])
    best = None
    for order in _corner_orders(corners):
        feats = square_features(warp_board(frame, order))
        if not _orientation_ok(feats):
            continue
        centroids = fit_centroids(feats)
        scatter = _scatter(feats, centroids)
        if best is None or scatter < best[0]:
            best = (scatter, order, feats, centroids)
    if best is None:
        return None

    _, order, feats, centroids = best
    occupancy, low_confidence = classify(feats, centroids)
    h, w = frame.shape[:2]
    levels = marker_levels(frame, markers_px) if markers_px is not None else None
    return {
        "corners_px": [[round(x, 1), round(y, 1)] for x, y in order],
        "frame_size": [w, h],
        "centroids": centroids,
        "markers_px": [[[round(x, 1), round(y, 1)] for x, y in m] for m in markers_px] if levels else None,
        "levels": [round(levels[0], 1), round(levels[1], 1)] if levels else None,
        "occupancy": occupancy,
        "low_confidence": low_confidence,
    }


def analyze_frame(frame, calib):
    """Frame + calibration -> (warped image, occupancy, low-confidence squares)."""
    warped = warp_board(frame, calib["corners_px"])
    feats = match_lighting(square_features(warped), frame, calib)
    occupancy, low_confidence = classify(feats, calib["centroids"])
    return warped, occupancy, low_confidence


def draw_debug(warped, occupancy, low_confidence):
    """Warped board with grid lines and the detected color of each square."""
    img = warped.copy()
    for k in range(9):
        cv2.line(img, (k * CELL, 0), (k * CELL, WARP_SIZE), (0, 255, 0), 1)
        cv2.line(img, (0, k * CELL), (WARP_SIZE, k * CELL), (0, 255, 0), 1)
    low = set(low_confidence)
    for i, ch in enumerate(occupancy):
        x0, y0, _, _ = square_rect(i)
        name = chess.square_name(i)
        color = (0, 0, 255) if name in low else (0, 255, 0)
        cv2.putText(img, name, (x0 + 3, y0 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        if ch != ".":
            cv2.putText(img, ch, (x0 + CELL // 2 - 10, y0 + CELL // 2 + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    return img
