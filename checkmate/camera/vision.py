"""Board image processing: warp, per-square features, classification, calibration fit.

Pure functions on numpy images, so they can be tested with synthetic pictures.
"""

import chess
import cv2
import numpy as np

# Top-down board image: WARP_SIZE x WARP_SIZE pixels, a8 at top-left, h1 at bottom-right.
WARP_SIZE = 640
CELL = WARP_SIZE // 8

# Fraction of each square (centered) used for classification; edges are noisy.
PATCH_FRACTION = 0.5

# A square is "low confidence" if (nearest distance / second nearest distance) is above this.
LOW_CONFIDENCE_RATIO = 0.7

CLASSES = ("empty", "W", "B")
CLASS_CHAR = {"empty": ".", "W": "W", "B": "B"}


def square_rect(i):
    """Pixel rect (x0, y0, x1, y1) of square index i in the warped image."""
    file, rank = i % 8, i // 8
    x0, y0 = file * CELL, (7 - rank) * CELL
    return x0, y0, x0 + CELL, y0 + CELL


def is_dark_square(i):
    # a1 (file 0, rank 0) is dark.
    return (i % 8 + i // 8) % 2 == 0


def warp_board(frame, corners_px):
    """Perspective-warp `frame` to a top-down board. corners_px order: a1, h1, h8, a8."""
    src = np.array(corners_px, dtype=np.float32)
    dst = np.array([[0, WARP_SIZE], [WARP_SIZE, WARP_SIZE], [WARP_SIZE, 0], [0, 0]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(frame, m, (WARP_SIZE, WARP_SIZE))


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


def _start_label(i):
    rank = i // 8
    if rank <= 1:
        return "W"
    if rank >= 6:
        return "B"
    return "empty"


def fit_centroids(feats):
    """Class centroids from a board in the starting position, separately for light and dark squares."""
    centroids = {}
    for shade, dark in (("dark", True), ("light", False)):
        centroids[shade] = {}
        for cls in CLASSES:
            idx = [i for i in range(64) if is_dark_square(i) == dark and _start_label(i) == cls]
            centroids[shade][cls] = feats[idx].mean(axis=0).tolist()
    return centroids


def classify(feats, centroids):
    """Nearest-centroid classification -> (occupancy string, list of low-confidence squares)."""
    chars, low = [], []
    for i in range(64):
        cents = centroids["dark" if is_dark_square(i) else "light"]
        dists = sorted((float(np.linalg.norm(feats[i] - np.array(cents[c]))), c) for c in CLASSES)
        chars.append(CLASS_CHAR[dists[0][1]])
        if dists[1][0] > 0 and dists[0][0] / dists[1][0] > LOW_CONFIDENCE_RATIO:
            low.append(chess.square_name(i))
    return "".join(chars), low


def _orientation_ok(feats):
    """True if the warped board shows the starting position the right way round.

    - empty dark squares must be darker than empty light squares (catches 90° turns / mirroring)
    - ranks 1-2 (white pieces) must be brighter than ranks 7-8 (catches 180° turns)
    """
    empty = [i for i in range(64) if _start_label(i) == "empty"]
    dark = np.mean([feats[i, 0] for i in empty if is_dark_square(i)])
    light = np.mean([feats[i, 0] for i in empty if not is_dark_square(i)])
    white = np.mean([feats[i, 0] for i in range(64) if _start_label(i) == "W"])
    black = np.mean([feats[i, 0] for i in range(64) if _start_label(i) == "B"])
    return dark < light and white > black


def calibrate_from_frame(frame, corners_px):
    """Fit a calibration from one frame of the board in the starting position.

    Tries the 4 rotations of `corners_px` and keeps the one where a1 is a dark square and the
    white pieces are on ranks 1-2. Returns a calibration dict, or None if no rotation fits.
    """
    corners = [list(map(float, c)) for c in corners_px]
    for shift in range(4):
        rotated = corners[shift:] + corners[:shift]
        feats = square_features(warp_board(frame, rotated))
        if not _orientation_ok(feats):
            continue
        centroids = fit_centroids(feats)
        occupancy, low = classify(feats, centroids)
        h, w = frame.shape[:2]
        return {
            "corners_px": [[round(x, 1), round(y, 1)] for x, y in rotated],
            "frame_size": [w, h],
            "centroids": centroids,
            "occupancy": occupancy,
            "low_confidence": low,
        }
    return None


def analyze_frame(frame, calib):
    """Frame + calibration -> (warped image, occupancy, low-confidence squares)."""
    warped = warp_board(frame, calib["corners_px"])
    occupancy, low = classify(square_features(warped), calib["centroids"])
    return warped, occupancy, low


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
