"""Camera class with a fake frame source that returns synthetic images."""

import time

import pytest

from checkmate.camera import Camera, occupancy_from_fen, sources
from tests.camera.synthetic import AFTER_E4, FRAME_H, FRAME_W, START_OCC, expected_corners, render


class _FakeSource:
    frame = None

    def __init__(self, *args):
        pass

    def read(self):
        time.sleep(0.01)
        return _FakeSource.frame

    def close(self):
        pass


def _wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = cond()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("timed out")


def test_camera_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "V4l2Source", _FakeSource)
    _FakeSource.frame = render(START_OCC)
    config = {"backend": "v4l2", "width": FRAME_W, "height": FRAME_H,
              "calibration_file": str(tmp_path / "calibration.json"), "stable_time_s": 0.2}

    cam = Camera(config)
    assert cam.get_observation()["error"] == "CAMERA_NOT_READY"
    assert cam.start() == {"ok": True, "calibrated": False}
    _wait_for(lambda: cam.get_debug_image())  # raw frame available
    assert cam.get_observation()["error"] == "CAMERA_NOT_READY"

    r = cam.calibrate()
    assert r["ok"], r
    assert r["occupancy"] == START_OCC
    assert r["frame_size"] == [FRAME_W, FRAME_H]

    obs = _wait_for(lambda: (o := cam.get_observation())["ok"] and o["stable"] and o)
    assert obs["occupancy"] == START_OCC

    # Hand over the board: unstable, then stable again with the new position.
    _FakeSource.frame = render(occupancy_from_fen(AFTER_E4))
    after = occupancy_from_fen(AFTER_E4)
    obs = _wait_for(lambda: (o := cam.get_observation())["stable"] and o["occupancy"] == after and o)
    assert obs["seq"] > 1
    assert isinstance(cam.get_debug_image(), bytes)
    cam.close()
    cam.close()

    # Calibration is loaded from the file on the next start.
    cam2 = Camera(config)
    assert cam2.start() == {"ok": True, "calibrated": True}
    cam2.close()


def test_camera_manual_corners(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "V4l2Source", _FakeSource)
    _FakeSource.frame = render(START_OCC, markers=False)
    cam = Camera({"backend": "v4l2", "calibration_file": str(tmp_path / "c.json"),
                  "manual_corners": expected_corners()})
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    r = cam.calibrate()
    assert r["ok"] and r["occupancy"] == START_OCC
    cam.close()


def test_camera_calibration_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "V4l2Source", _FakeSource)
    _FakeSource.frame = render(START_OCC, markers=False)
    cam = Camera({"backend": "v4l2", "calibration_file": str(tmp_path / "c.json")})
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    assert cam.calibrate()["error"] == "CALIBRATION_FAILED"
    cam.close()


def test_camera_bad_config():
    with pytest.raises(ValueError):
        Camera({"backend": "nope"})


def test_camera_open_failure(tmp_path):
    cam = Camera({"backend": "v4l2", "device_index": 99, "calibration_file": str(tmp_path / "c.json")})
    r = cam.start()
    assert r["ok"] is False and r["error"] == "CAMERA_NOT_READY"
    cam.close()
