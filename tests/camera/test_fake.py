from checkmate.camera import START_FEN, FakeCamera, occupancy_from_fen


def test_fake_camera():
    cam = FakeCamera({})
    assert cam.get_observation()["error"] == "CAMERA_NOT_READY"
    assert cam.start() == {"ok": True, "calibrated": True}

    obs = cam.get_observation()
    assert obs["ok"] and obs["stable"]
    assert obs["occupancy"] == occupancy_from_fen(START_FEN)

    cam.occupancy = "WWWWWWWWWWWW.WWW............W...................BBBBBBBBBBBBBBBB"
    cam.stable = False
    obs2 = cam.get_observation()
    assert obs2["occupancy"] == cam.occupancy
    assert obs2["stable"] is False
    assert obs2["seq"] == obs["seq"] + 1

    assert cam.calibrate()["ok"]
    assert cam.get_debug_image() is None
    cam.close()
    cam.close()
