"""Vision pipeline on synthetic images: calibration, classification, ArUco. No camera needed."""

import chess
import numpy as np
import pytest

from checkmate.camera import START_FEN, detect_move, occupancy_from_fen
from checkmate.camera.aruco import find_aruco_corners
from checkmate.camera.vision import analyze_frame, calibrate_from_frame, square_rect
from tests.camera.synthetic import AFTER_E4, START_OCC, expected_corners, render


def _close(a, b, tol=3.0):
    return np.allclose(np.array(a), np.array(b), atol=tol)


def test_calibrate_and_classify_start():
    calib = calibrate_from_frame(render(START_OCC), expected_corners())
    assert calib is not None
    assert calib["occupancy"] == START_OCC
    assert _close(calib["corners_px"], expected_corners())


@pytest.mark.parametrize("shift", [1, 2, 3])
def test_calibrate_fixes_orientation(shift):
    corners = expected_corners()
    calib = calibrate_from_frame(render(START_OCC), corners[shift:] + corners[:shift])
    assert calib is not None
    assert _close(calib["corners_px"], corners)
    assert calib["occupancy"] == START_OCC


def test_calibrate_rejects_empty_board():
    assert calibrate_from_frame(render("." * 64), expected_corners()) is None


def test_move_detected_from_image():
    calib = calibrate_from_frame(render(START_OCC), expected_corners())
    _, occ, _ = analyze_frame(render(occupancy_from_fen(AFTER_E4)), calib)
    assert occ == occupancy_from_fen(AFTER_E4)
    assert detect_move(START_FEN, occ) == {"ok": True, "status": "move", "move": "e2e4"}


def test_find_aruco_corners():
    corners = find_aruco_corners(render(START_OCC))
    assert corners is not None
    assert _close(corners, expected_corners(), tol=4.0)


def test_find_aruco_corners_missing():
    assert find_aruco_corners(render(START_OCC, markers=False)) is None


def test_square_names_match_warp_layout():
    # a8 is top-left, h1 bottom-right in the warped image.
    assert square_rect(chess.A8)[:2] == (0, 0)
    assert square_rect(chess.H1)[2:] == (640, 640)
