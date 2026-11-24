"""Vision pipeline on synthetic images: calibration, classification, ArUco. No camera needed."""

import itertools

import chess
import cv2
import numpy as np
import pytest

from checkmate.camera import START_FEN, detect_move, occupancy_from_fen
from checkmate.camera.aruco import board_corners, find_aruco_corners, find_aruco_markers, marker_levels
from checkmate.camera.vision import analyze_frame, calibrate_from_frame, square_rect
from tests.camera import synthetic
from tests.camera.synthetic import AFTER_E4, SKIN, START_OCC, expected_corners, render


def _close(a, b, tol=3.0):
    return np.allclose(np.array(a), np.array(b), atol=tol)


def _calibrate(frame):
    """Calibrate like Camera.calibrate() does with the markers."""
    markers = find_aruco_markers(frame)
    return calibrate_from_frame(frame, board_corners(markers), markers)


def _cover(frame, marker):
    """A hand over one marker."""
    cv2.fillConvexPoly(frame, np.int32(marker), SKIN)
    return frame


def test_calibrate_and_classify_start():
    calib = calibrate_from_frame(render(START_OCC), expected_corners())
    assert calib is not None
    assert calib["occupancy"] == START_OCC
    assert _close(calib["corners_px"], expected_corners())
    assert calib["markers_px"] is None and calib["levels"] is None  # manual corners: no markers


@pytest.mark.parametrize("shift", [1, 2, 3])
def test_calibrate_fixes_orientation(shift):
    corners = expected_corners()
    calib = calibrate_from_frame(render(START_OCC), corners[shift:] + corners[:shift])
    assert calib is not None
    assert _close(calib["corners_px"], corners)
    assert calib["occupancy"] == START_OCC


@pytest.mark.parametrize("shift", [0, 1, 2, 3])
def test_calibrate_fixes_mirrored_corners(shift):
    # Corners listed the wrong way round (a1, a8, h8, h1): a diagonal mirror keeps the square colors.
    a1, h1, h8, a8 = expected_corners()
    mirrored = [a1, a8, h8, h1]
    calib = calibrate_from_frame(render(START_OCC), mirrored[shift:] + mirrored[:shift])
    assert calib is not None
    assert _close(calib["corners_px"], expected_corners())
    assert calib["occupancy"] == START_OCC


@pytest.mark.parametrize("ids", list(itertools.permutations(range(4))))
def test_markers_in_any_corner(monkeypatch, ids):
    # People can't read a marker's number, so any marker may sit at any corner; the pieces say
    # which corner is a1.
    monkeypatch.setattr(synthetic, "ARUCO_IDS", dict(zip(["a1", "h1", "h8", "a8"], ids)))
    calib = _calibrate(render(START_OCC))
    assert calib["occupancy"] == START_OCC
    assert _close(calib["corners_px"], expected_corners(), tol=4.0)


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
    assert find_aruco_markers(render(START_OCC, markers=False)) is None


def test_find_aruco_markers():
    markers = find_aruco_markers(render(START_OCC))
    assert len(markers) == 4 and all(len(m) == 4 for m in markers)
    assert _close(board_corners(markers), expected_corners(), tol=4.0)


def test_marker_levels_follow_the_light():
    markers = find_aruco_markers(render(START_OCC))
    black, white = marker_levels(render(START_OCC), markers)
    dim_black, dim_white = marker_levels(render(START_OCC, light=0.6), markers)
    assert white - black > 150
    assert dim_white < white - 50 and dim_black <= black + 5


def test_marker_levels_skip_covered_markers():
    markers = find_aruco_markers(render(START_OCC))
    one_covered = _cover(render(START_OCC), markers[0])
    assert marker_levels(one_covered, markers) == pytest.approx(marker_levels(render(START_OCC), markers), abs=3)
    all_covered = render(START_OCC)
    for marker in markers:
        _cover(all_covered, marker)
    assert marker_levels(all_covered, markers) is None


def test_calibration_keeps_the_markers():
    calib = _calibrate(render(START_OCC))
    assert calib["occupancy"] == START_OCC
    assert len(calib["markers_px"]) == 4 and len(calib["levels"]) == 2


@pytest.mark.parametrize("calibrated, now", [
    ({}, {"light": 0.6}),                  # the room got darker
    ({"light": 0.7}, {"light": 0.95}),     # ... or brighter (without saturating)
    ({}, {"light": 0.75, "glare": 40}),    # washed out: glare on a screen
])
def test_move_detected_after_the_light_changes(calibrated, now):
    calib = _calibrate(render(START_OCC, **calibrated))
    _, occ, _ = analyze_frame(render(occupancy_from_fen(AFTER_E4), **now), calib)
    assert occ == occupancy_from_fen(AFTER_E4)
    assert detect_move(START_FEN, occ)["move"] == "e2e4"


def test_light_change_with_a_marker_covered():
    calib = _calibrate(render(START_OCC))
    frame = _cover(render(occupancy_from_fen(AFTER_E4), light=0.6), calib["markers_px"][0])
    _, occ, _ = analyze_frame(frame, calib)
    assert occ == occupancy_from_fen(AFTER_E4)


def test_no_clear_marker_leaves_the_squares_as_they_are():
    calib = _calibrate(render(START_OCC))
    frame = render(occupancy_from_fen(AFTER_E4))
    for marker in calib["markers_px"]:
        _cover(frame, marker)
    _, occ, _ = analyze_frame(frame, calib)
    assert occ == occupancy_from_fen(AFTER_E4)


def test_square_names_match_warp_layout():
    # a8 is top-left, h1 bottom-right in the warped image.
    assert square_rect(chess.A8)[:2] == (0, 0)
    assert square_rect(chess.H1)[2:] == (640, 640)
