"""Camera class with a fake frame source that returns synthetic images."""

import time

import cv2
import pytest

from checkmate.camera import Camera, occupancy_from_fen, sources
from tests.camera.synthetic import AFTER_E4, FRAME_H, FRAME_W, START_OCC, expected_corners, render


class _FakeSource:
    frame = None
    opened = 0

    def __init__(self, *args):
        _FakeSource.opened += 1

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


def _stable_obs(cam, occupancy):
    return _wait_for(lambda: (o := cam.get_observation())["ok"] and o["stable"]
                     and o["occupancy"] == occupancy and o)


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "V4l2Source", _FakeSource)
    _FakeSource.frame = render(START_OCC)
    return {"backend": "v4l2", "width": FRAME_W, "height": FRAME_H,
            "calibration_file": str(tmp_path / "calibration.json"), "stable_time_s": 0.2}


def test_camera_end_to_end(config):
    cam = Camera(config)
    assert cam.get_observation()["error"] == "CAMERA_NOT_READY"
    assert cam.start() == {"ok": True, "calibrated": False}
    _wait_for(lambda: cam.get_debug_image())  # raw frame available
    assert cam.get_observation()["error"] == "CAMERA_NOT_READY"

    r = cam.calibrate()
    assert r["ok"], r
    assert r["occupancy"] == START_OCC
    assert r["frame_size"] == [FRAME_W, FRAME_H]
    _stable_obs(cam, START_OCC)

    # Hand over the board: unstable, then stable again with the new position.
    _FakeSource.frame = render(START_OCC, hand=True)
    _wait_for(lambda: cam.get_observation()["stable"] is False)
    _FakeSource.frame = render(occupancy_from_fen(AFTER_E4))
    obs = _stable_obs(cam, occupancy_from_fen(AFTER_E4))
    assert obs["seq"] > 1
    assert isinstance(cam.get_debug_image(), bytes)
    cam.close()
    cam.close()

    # Calibration is loaded from the file on the next start.
    cam2 = Camera(config)
    assert cam2.start() == {"ok": True, "calibrated": True}
    cam2.close()


def test_camera_manual_corners(config):
    _FakeSource.frame = render(START_OCC, markers=False)
    cam = Camera({**config, "manual_corners": expected_corners()})
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    r = cam.calibrate()
    assert r["ok"] and r["occupancy"] == START_OCC
    cam.close()


def test_camera_calibration_failed(config):
    _FakeSource.frame = render(START_OCC, markers=False)
    cam = Camera(config)
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    assert cam.calibrate()["error"] == "CALIBRATION_FAILED"
    cam.close()


def test_camera_stopped_sending_frames(config, monkeypatch):
    monkeypatch.setattr("checkmate.camera.camera.FRAME_TIMEOUT_S", 0.3)
    cam = Camera(config)
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    assert cam.calibrate()["ok"]
    _stable_obs(cam, START_OCC)

    # start() while frames arrive does nothing.
    opened = _FakeSource.opened
    assert cam.start() == {"ok": True, "calibrated": True}
    assert _FakeSource.opened == opened

    _FakeSource.frame = None
    _wait_for(lambda: "no frames" in cam.get_observation().get("message", ""))
    assert cam.calibrate()["error"] == "CAMERA_NOT_READY"

    # retry (section 6): start() reopens the camera.
    _FakeSource.frame = render(START_OCC)
    assert cam.start() == {"ok": True, "calibrated": True}
    assert _FakeSource.opened == opened + 1
    _stable_obs(cam, START_OCC)
    cam.close()


def test_camera_corrupt_calibration_file(config, tmp_path):
    (tmp_path / "calibration.json").write_text("{not json")
    cam = Camera(config)
    assert cam.start() == {"ok": True, "calibrated": False}
    _wait_for(lambda: cam.get_debug_image())
    assert cam.calibrate()["ok"]
    _stable_obs(cam, START_OCC)
    cam.close()


def test_camera_resolution_changed(config):
    cam = Camera(config)
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    assert cam.calibrate()["ok"]
    cam.close()

    _FakeSource.frame = cv2.resize(render(START_OCC), (FRAME_W // 2, FRAME_H // 2))
    cam = Camera(config)
    assert cam.start() == {"ok": True, "calibrated": True}
    r = _wait_for(lambda: "calibrate again" in cam.get_observation().get("message", "") and cam.get_observation())
    assert r["error"] == "CAMERA_NOT_READY"
    cam.close()


def test_camera_bad_config():
    with pytest.raises(ValueError):
        Camera({"backend": "nope"})


def test_camera_open_failure(tmp_path):
    cam = Camera({"backend": "v4l2", "device_index": 99, "calibration_file": str(tmp_path / "c.json")})
    r = cam.start()
    assert r["ok"] is False and r["error"] == "CAMERA_NOT_READY"
    cam.close()
