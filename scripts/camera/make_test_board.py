"""Draw top-down test boards with the pieces and the 4 ArUco markers, for trying the camera
without the real board: show an image on a tablet or monitor (or print it) under the camera.

One image per position: the starting position (calibrate on it), then one after each move.
The pieces are plain discs, as the camera only tells empty, white and black apart (section 1.2).

Usage: python scripts/camera/make_test_board.py [out_dir] [uci_move ...]
       (default: test_board/ with the start and e2e4)
"""

import sys
from pathlib import Path

import chess
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from checkmate.camera.aruco import ARUCO_IDS, marker_image  # noqa: E402

SQ = 100                    # pixels per square; markers are one square, like the real board
QUIET = SQ // 2             # white around the markers, so they can be detected
BOARD_AT = QUIET + SQ       # the a8 corner of the board on the image
SIDE = 2 * BOARD_AT + 8 * SQ
CAPTION_H = 70

# BGR. Far apart in lightness (what the camera compares): white > light > dark > black.
LIGHT = (175, 200, 215)
DARK = (85, 135, 105)
WHITE_PIECE = (255, 255, 255)
BLACK_PIECE = (25, 25, 25)
OUTLINE = (110, 110, 110)
RADIUS = int(SQ * 0.38)     # covers the middle half of the square that the camera reads


def render(board: chess.Board, caption: str):
    img = np.full((SIDE + CAPTION_H, SIDE, 3), 255, np.uint8)
    for square in chess.SQUARES:
        file, rank = chess.square_file(square), chess.square_rank(square)
        x0, y0 = BOARD_AT + file * SQ, BOARD_AT + (7 - rank) * SQ
        color = DARK if (file + rank) % 2 == 0 else LIGHT  # a1 is dark
        cv2.rectangle(img, (x0, y0), (x0 + SQ - 1, y0 + SQ - 1), color, -1)
        piece = board.piece_at(square)
        if piece:
            center = (x0 + SQ // 2, y0 + SQ // 2)
            cv2.circle(img, center, RADIUS, WHITE_PIECE if piece.color == chess.WHITE else BLACK_PIECE, -1)
            cv2.circle(img, center, RADIUS, OUTLINE, 2)

    # Each marker's inner corner touches its board corner: a1 bottom left, h1 bottom right, ...
    lo, hi = BOARD_AT - SQ, BOARD_AT + 8 * SQ
    for corner, (x, y) in {"a1": (lo, hi), "h1": (hi, hi), "h8": (hi, lo), "a8": (lo, lo)}.items():
        img[y:y + SQ, x:x + SQ] = cv2.cvtColor(marker_image(ARUCO_IDS[corner], SQ), cv2.COLOR_GRAY2BGR)

    cv2.putText(img, caption, (QUIET, SIDE + CAPTION_H // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (60, 60, 60), 2)
    return img


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "test_board")
    moves = sys.argv[2:] if len(sys.argv) > 2 else ["e2e4"]

    board = chess.Board()
    images = [("00_start", render(board, "start position: calibrate on this one"))]
    for n, uci in enumerate(moves, 1):
        try:
            board.push_uci(uci)
        except ValueError:
            sys.exit(f"{uci} is not a legal move after {' '.join(moves[:n - 1]) or 'the start'}")
        images.append((f"{n:02d}_{uci}", render(board, f"after {' '.join(moves[:n])}")))

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, img in images:
        path = out_dir / f"{name}.png"
        cv2.imwrite(str(path), img)
        print(path)


if __name__ == "__main__":
    main()
