"""Calibration file save / load."""

import pytest

from checkmate.camera.calibration import load_calibration, save_calibration
from checkmate.camera.vision import calibrate_from_frame
from tests.camera.synthetic import START_OCC, expected_corners, render


def test_round_trip(tmp_path):
    calib = calibrate_from_frame(render(START_OCC), expected_corners())
    path = tmp_path / "c.json"
    saved = save_calibration(path, calib)
    assert set(saved) == {"corners_px", "frame_size", "centroids"}
    assert load_calibration(path) == saved


@pytest.mark.parametrize("content", [
    "{not json",
    "[]",
    '{"corners_px": [[0, 0]], "frame_size": [1280, 720], "centroids": {}}',
    # older format: classes named "empty" instead of "."
    '{"corners_px": [[0,0],[1,0],[1,1],[0,1]], "frame_size": [1280, 720], "centroids": '
    '{"dark": {"empty": [0, 0], "W": [0, 0], "B": [0, 0]}, "light": {"empty": [0, 0], "W": [0, 0], "B": [0, 0]}}}',
])
def test_bad_file_is_ignored(tmp_path, content):
    path = tmp_path / "c.json"
    path.write_text(content)
    assert load_calibration(path) is None


def test_missing_file(tmp_path):
    assert load_calibration(tmp_path / "missing.json") is None
