"""FakeLedController (section 4.4): always ok, prints an 8x8 grid with rank 8 on top."""

from checkmate.led import FakeLedController


def test_every_method_is_ok():
    led = FakeLedController({})
    assert led.start() == {"ok": True, "fw": "fake"}
    for res in (led.show([]), led.clear(), led.set_brightness(30), led.self_test()):
        assert res == {"ok": True}
    assert led.is_connected() is True
    led.close()


def test_show_prints_the_grid(capsys):
    FakeLedController().show([{"sq": "a8", "role": "engine_from"}, {"sq": "h1", "role": "error"}])
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "  a b c d e f g h"
    assert lines[2] == "8 F . . . . . . ."  # rank 8 on top
    assert lines[9] == "1 . . . . . . . X"
    assert lines[10] == "  F engine_from, X error"


def test_bad_show_warns_but_is_ok(capsys):
    assert FakeLedController().show([{"sq": "z9", "role": "error"}]) == {"ok": True}
    assert "BAD_REQUEST" in capsys.readouterr().out
