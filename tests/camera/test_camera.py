"""Camera class with a fake frame source that returns synthetic images."""

import time

import cv2
import numpy as np
import pytest

import checkmate.camera.camera as camera_module
from checkmate.camera import Camera, occupancy_from_fen, sources
from checkmate.camera.ai_reader import AI_SIZE
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

    # The room gets darker: the same position, corrected by the markers' black and white.
    _FakeSource.frame = render(occupancy_from_fen(AFTER_E4), light=0.6)
    _stable_obs(cam, occupancy_from_fen(AFTER_E4))
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
    with pytest.raises(ValueError):
        Camera({"backend": "v4l2", "classifier": "magic"})


class _FakeAiReader:
    """Stands in for DeepSeekReader: answers with `occupancy`, which a test sets with the frame."""
    occupancy = None
    calls = 0
    error = None

    def __init__(self, config):
        pass

    def read(self, jpeg):
        _FakeAiReader.calls += 1
        _FakeAiReader.last_jpeg = jpeg
        if _FakeAiReader.error:
            return {"ok": False, "error": "AI_UNAVAILABLE", "message": _FakeAiReader.error}
        return {"ok": True, "occupancy": _FakeAiReader.occupancy, "obstructed": False}


@pytest.fixture
def ai_config(config, monkeypatch):
    monkeypatch.setattr(camera_module, "DeepSeekReader", _FakeAiReader)
    _FakeAiReader.occupancy, _FakeAiReader.calls, _FakeAiReader.error = START_OCC, 0, None
    return {**config, "classifier": "ai", "ai": {"retry_s": 0.05, "give_up_s": 0.3}}


def test_ai_image_without_the_ai(config):
    # classifier "opencv": the picture the model would get, made from the current frame
    cam = Camera(config)
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    frame = cv2.imdecode(np.frombuffer(cam.get_frame_image(), np.uint8), cv2.IMREAD_COLOR)
    assert frame.shape == (FRAME_H, FRAME_W, 3)  # the frame as the camera took it
    assert cam.get_ai_image() is None  # not calibrated: no board to straighten
    assert cam.calibrate()["ok"]
    img = cv2.imdecode(np.frombuffer(_wait_for(cam.get_ai_image), np.uint8), cv2.IMREAD_COLOR)
    assert img.shape == (AI_SIZE, AI_SIZE, 3)
    assert cam.get_ai_image(sent=True) is None  # nothing is sent with classifier "opencv"
    cam.close()


def test_camera_reads_the_board_with_the_ai(ai_config):
    cam = Camera(ai_config)
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    assert cam.calibrate()["ok"]
    assert _stable_obs(cam, START_OCC)["low_confidence"] == []
    assert cam.get_ai_image(sent=True) == _FakeAiReader.last_jpeg  # the picture actually sent
    calls = _FakeAiReader.calls

    # A move: a hand over the board, then the new position, read once it is still.
    after = occupancy_from_fen(AFTER_E4)
    _FakeAiReader.occupancy = after
    _FakeSource.frame = render(START_OCC, hand=True)
    _wait_for(lambda: cam.get_observation()["stable"] is False)
    _FakeSource.frame = render(after)
    _stable_obs(cam, after)
    assert calls < _FakeAiReader.calls <= calls + 2  # maybe the hand too, if it stayed still

    # Nothing moves: no more reads.
    calls = _FakeAiReader.calls
    time.sleep(0.4)
    assert _FakeAiReader.calls == calls and cam.get_observation()["stable"]
    cam.close()


def test_camera_says_so_when_the_ai_cant_be_reached(ai_config):
    _FakeAiReader.error = "no route to api.deepseek.com"
    cam = Camera(ai_config)
    cam.start()
    _wait_for(lambda: cam.get_debug_image())
    assert cam.calibrate()["ok"]
    obs = _wait_for(lambda: "AI" in (o := cam.get_observation()).get("message", "") and o)
    assert obs == {"ok": False, "error": "CAMERA_NOT_READY",
                   "message": "can't read the board with the AI: no route to api.deepseek.com"}
    assert _FakeAiReader.calls > 1  # it kept trying

    _FakeAiReader.error = None  # back online
    _stable_obs(cam, START_OCC)
    cam.close()


def test_camera_open_failure(tmp_path):
    cam = Camera({"backend": "v4l2", "device_index": 99, "calibration_file": str(tmp_path / "c.json")})
    r = cam.start()
    assert r["ok"] is False and r["error"] == "CAMERA_NOT_READY"
    cam.close()
