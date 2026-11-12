"""LedController driving WS2812 over SPI (contracts/interfaces.md section 4.1).

No hardware: `open_spi` is replaced with a fake SPI device that records what was written.
"""

import pytest

import checkmate.led.controller as controller_mod
from checkmate.led import LedController


class FakeSpi:
    def __init__(self):
        self.writes = []
        self.closed = False
        self.fail = False  # when True, writes raise (simulates the device going away)

    def writebytes2(self, data):
        if self.fail:
            raise OSError("spi gone")
        self.writes.append(bytes(data))

    def close(self):
        self.closed = True


@pytest.fixture
def spi(monkeypatch):
    """Install a working fake SPI device and hand the test the instance."""
    dev = FakeSpi()
    monkeypatch.setattr(controller_mod, "open_spi", lambda bus, device, hz: dev)
    return dev


@pytest.fixture
def led(spi):
    c = LedController({"brightness": 40})
    c.start()
    yield c
    c.close()


# -- construction --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [-1, 101, "40", 3.0, True])
def test_bad_brightness_in_config_raises(bad):
    with pytest.raises(ValueError):
        LedController({"brightness": bad})


# -- lifecycle -----------------------------------------------------------------------------

def test_start_connects_and_reports_firmware(spi):
    c = LedController({})
    res = c.start()
    assert res["ok"] is True and "fw" in res
    assert c.is_connected() is True
    assert spi.writes, "boot should have written the corner pattern"
    c.close()


def test_close_is_safe_twice(led):
    led.close()
    led.close()
    assert led.is_connected() is False


# -- commands ------------------------------------------------------------------------------

def test_show_clear_brightness_selftest(led):
    assert led.show([{"sq": "e7", "role": "engine_from"}, {"sq": "e5", "role": "engine_to"}]) == {"ok": True}
    assert led.clear() == {"ok": True}
    assert led.set_brightness(20) == {"ok": True}
    assert led.self_test() == {"ok": True}


@pytest.mark.parametrize("squares,code", [
    ("not-a-list", "BAD_REQUEST"),
    ([{"sq": "z9", "role": "engine_to"}], "BAD_REQUEST"),
    ([{"sq": "e4", "role": "bogus"}], "BAD_REQUEST"),
    ([{"sq": "e4", "role": "check"}, {"sq": "e4", "role": "error"}], "BAD_REQUEST"),
])
def test_show_rejects_bad_patterns(led, squares, code):
    assert led.show(squares)["error"] == code


@pytest.mark.parametrize("bad", [-1, 101, "20", 2.5, True])
def test_set_brightness_bad_request(led, bad):
    assert led.set_brightness(bad)["error"] == "BAD_REQUEST"


# -- graceful degradation (section 6: LED failure is not fatal) ----------------------------

def test_start_without_device_is_disconnected_not_fatal(monkeypatch):
    def boom(bus, device, hz):
        raise FileNotFoundError("/dev/spidev0.0")
    monkeypatch.setattr(controller_mod, "open_spi", boom)
    c = LedController({})
    res = c.start()
    assert res["error"] == "LED_DISCONNECTED"
    assert c.is_connected() is False
    # Commands still return cleanly (never raise), so the game continues without LEDs.
    assert c.show([{"sq": "e2", "role": "engine_from"}])["error"] == "LED_DISCONNECTED"
    assert c.clear()["error"] == "LED_DISCONNECTED"
    c.close()


def test_write_failure_marks_disconnected(led, spi):
    spi.fail = True
    res = led.show([{"sq": "e4", "role": "engine_to"}])
    assert res["error"] == "LED_DISCONNECTED"
    assert led.is_connected() is False
