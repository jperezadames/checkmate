"""Draw a synthetic chessboard photo for tests: board in perspective, optional ArUco markers."""

import cv2
import numpy as np

from checkmate.camera import START_FEN, occupancy_from_fen

BOARD = 640
SQ = BOARD // 8
MARKER = 100
MARGIN = 140
CANVAS = BOARD + 2 * MARGIN
FRAME_W, FRAME_H = 1280, 720

LIGHT = (181, 217, 240)
DARK = (99, 136, 181)

# Where the canvas corners land in the camera frame (a slightly tilted view).
CANVAS_IN_FRAME = np.float32([[300, 20], [990, 50], [1060, 700], [230, 690]])  # TL, TR, BR, BL

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _canvas_to_frame_matrix():
    src = np.float32([[0, 0], [CANVAS, 0], [CANVAS, CANVAS], [0, CANVAS]])
    return cv2.getPerspectiveTransform(src, CANVAS_IN_FRAME)


def expected_corners():
    """Board corners a1, h1, h8, a8 in frame pixels."""
    m = MARGIN
    pts = np.float32([[[m, m + BOARD]], [[m + BOARD, m + BOARD]], [[m + BOARD, m]], [[m, m]]])
    return cv2.perspectiveTransform(pts, _canvas_to_frame_matrix()).reshape(4, 2).tolist()


def render(occupancy, markers=True):
    canvas = np.full((CANVAS, CANVAS, 3), 255, np.uint8)
    for i in range(64):
        file, rank = i % 8, i // 8
        x0, y0 = MARGIN + file * SQ, MARGIN + (7 - rank) * SQ
        dark = (file + rank) % 2 == 0
        cv2.rectangle(canvas, (x0, y0), (x0 + SQ - 1, y0 + SQ - 1), DARK if dark else LIGHT, -1)
        center = (x0 + SQ // 2, y0 + SQ // 2)
        if occupancy[i] == "W":
            cv2.circle(canvas, center, 28, (235, 235, 235), -1)
            cv2.circle(canvas, center, 28, (60, 60, 60), 2)
        elif occupancy[i] == "B":
            cv2.circle(canvas, center, 28, (30, 30, 30), -1)

    if markers:
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        lo, hi = MARGIN - MARKER, MARGIN + BOARD
        # id 0 a1 (bottom-left), 1 h1 (bottom-right), 2 h8 (top-right), 3 a8 (top-left)
        for marker_id, (x, y) in enumerate([(lo, hi), (hi, hi), (hi, lo), (lo, lo)]):
            img = cv2.aruco.generateImageMarker(dictionary, marker_id, MARKER)
            canvas[y:y + MARKER, x:x + MARKER] = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    return cv2.warpPerspective(canvas, _canvas_to_frame_matrix(), (FRAME_W, FRAME_H),
                               borderValue=(90, 90, 90))


START_OCC = occupancy_from_fen(START_FEN)
