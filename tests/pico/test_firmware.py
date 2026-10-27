"""pico/main.py under CPython (section 4.3): mapping, commands, blinking, and the real
LedController talking to it."""

import json
import time

import pytest

from checkmate.led import LedController
from checkmate.led import controller as led_controller
from pico import main as fw

OFF = (0, 0, 0)


class Strip(list):
    """Stands in for neopixel.NeoPixel."""

    def __init__(self):
        super().__init__([OFF] * fw.NUM_LEDS)
        self.writes = 0

    def write(self):
        self.writes += 1


@pytest.fixture
def leds():
    return fw.Leds(Strip())


def lit(leds):
    """{square: color} read back from the strip."""
    out = {}
    for f in fw.FILES:
        for r in fw.RANKS:
            colors = {leds.strip[i] for i in fw.led_indices(f + r)}
            assert len(colors) == 1, f + r  # all 4 LEDs of a square agree
            if colors != {OFF}:
                out[f + r] = colors.pop()
    return out


def send(leds, line, now=0):
    return json.loads(fw.handle_line(leds, line, now))


def scaled(color, percent):
    return tuple(int(c * percent / 100) for c in color)


# -- square -> LEDs --------------------------------------------------------------------------

def test_every_led_belongs_to_exactly_one_square():
    indices = [i for f in fw.FILES for r in fw.RANKS for i in fw.led_indices(f + r)]
    assert sorted(indices) == list(range(fw.NUM_LEDS))


def test_a1_is_at_the_strip_start():
    assert sorted(fw.led_indices("a1")) == [0, 1, 30, 31]  # serpentine: the 2nd row (16-31) runs backwards


# -- commands --------------------------------------------------------------------------------

def test_ping(leds):
    assert send(leds, '{"id": 1, "cmd": "ping"}') == {"id": 1, "ok": True, "fw": "checkmate-led 1.0"}


def test_set_lights_roles_in_their_colors(leds):
    reply = send(leds, json.dumps({"id": 3, "cmd": "set", "squares": [
        {"sq": "e1", "role": "engine_from"}, {"sq": "g1", "role": "engine_to"},
        {"sq": "d4", "role": "last_move"}]}))
    assert reply == {"id": 3, "ok": True}
    level = fw.DEFAULT_BRIGHTNESS
    assert lit(leds) == {"e1": scaled((0, 0, 255), level), "g1": scaled((0, 255, 0), level),
                         "d4": scaled((40, 40, 40), level)}


def test_set_replaces_and_clear_turns_off(leds):
    send(leds, '{"id": 1, "cmd": "set", "squares": [{"sq": "a1", "role": "check"}]}')
    send(leds, '{"id": 2, "cmd": "set", "squares": [{"sq": "b2", "role": "hint_to"}]}')
    assert list(lit(leds)) == ["b2"]
    assert send(leds, '{"id": 3, "cmd": "clear"}')["ok"] is True
    assert lit(leds) == {}


def test_brightness_keeps_the_pattern_and_is_capped(leds):
    send(leds, '{"id": 1, "cmd": "set", "squares": [{"sq": "a1", "role": "engine_to"}]}')
    assert send(leds, '{"id": 2, "cmd": "brightness", "value": 40}')["ok"] is True
    assert lit(leds) == {"a1": scaled((0, 255, 0), 40)}
    send(leds, '{"id": 3, "cmd": "brightness", "value": 100}')
    assert lit(leds) == {"a1": scaled((0, 255, 0), fw.MAX_BRIGHTNESS)}


@pytest.mark.parametrize("line,code", [
    ('{"id": 6, "cmd": "set", "squares": [{"sq": "z9", "role": "error"}]}', "BAD_SQUARE"),
    ('{"id": 6, "cmd": "set", "squares": [{"sq": "e4", "role": "sparkle"}]}', "BAD_ROLE"),
    ('{"id": 6, "cmd": "set", "squares": {"e4": "error"}}', "BAD_VALUE"),
    ('{"id": 6, "cmd": "brightness", "value": 150}', "BAD_VALUE"),
    ('{"id": 6, "cmd": "dance"}', "BAD_CMD"),
])
def test_errors(leds, line, code):
    reply = send(leds, line)
    assert reply["id"] == 6 and reply["ok"] is False and reply["error"] == code


@pytest.mark.parametrize("line", ["{not json", "[1, 2]"])
def test_bad_json_has_id_null(leds, line):
    assert send(leds, line)["error"] == "BAD_JSON"
    assert send(leds, line)["id"] is None


def test_too_long_line(leds):
    reader = fw.LineReader()
    for ch in "x" * (fw.MAX_LINE + 10):
        assert reader.feed(ch) is None
    reply = json.loads(fw.handle_line(leds, reader.feed("\n")))
    assert reply["error"] == "TOO_LONG" and reply["id"] is None
    # the next line is read normally
    line = None
    for ch in '{"id": 7, "cmd": "ping"}\n':
        line = reader.feed(ch)
    assert send(leds, line)["id"] == 7


def test_a_full_board_set_fits_in_one_line():
    squares = [{"sq": f + r, "role": "engine_from"} for f in fw.FILES for r in fw.RANKS]
    line = json.dumps({"id": 2**31, "cmd": "set", "squares": squares}, separators=(",", ":"))
    assert len(line) < fw.MAX_LINE


# -- timing: blinking, test, boot ------------------------------------------------------------

def test_error_blinks_at_2_hz_and_other_roles_stay(leds):
    send(leds, json.dumps({"id": 1, "cmd": "set", "squares": [
        {"sq": "e2", "role": "error"}, {"sq": "e4", "role": "check"}]}), now=1000)
    seen = []
    for now in (1000, 1249, 1250, 1499, 1500):
        leds.tick(now)
        seen.append(sorted(lit(leds)))
    assert seen == [["e2", "e4"], ["e2", "e4"], ["e4"], ["e4"], ["e2", "e4"]]


def test_test_lights_the_corners_one_by_one_then_off(leds):
    send(leds, '{"id": 1, "cmd": "set", "squares": [{"sq": "e4", "role": "check"}]}')
    assert send(leds, '{"id": 2, "cmd": "test"}', now=0)["ok"] is True  # replies right away
    seen = []
    for now in (0, 500, 1000, 1500, 2000):
        leds.tick(now)
        seen.append(list(lit(leds)))
    assert seen == [["a1"], ["h1"], ["h8"], ["a8"], []]


def test_a_command_stops_the_test(leds):
    send(leds, '{"id": 1, "cmd": "test"}', now=0)
    send(leds, '{"id": 2, "cmd": "set", "squares": [{"sq": "e4", "role": "check"}]}', now=600)
    leds.tick(1000)
    assert list(lit(leds)) == ["e4"]


def test_boot_check_lasts_1_s(leds):
    leds.boot(0)
    assert sorted(lit(leds)) == ["a1", "a8", "h1", "h8"]
    leds.tick(fw.BOOT_MS)
    assert lit(leds) == {}


def test_no_redraw_when_nothing_changes(leds):
    send(leds, '{"id": 1, "cmd": "set", "squares": [{"sq": "e4", "role": "check"}]}')
    writes = leds.strip.writes
    for now in range(0, 1000, 10):
        leds.tick(now)
    assert leds.strip.writes == writes


# -- the Pi side against this firmware -------------------------------------------------------

class SerialToFirmware:
    """A serial port with pico/main.py's handle_line behind it."""

    def __init__(self, leds):
        self.leds = leds
        self.reader = fw.LineReader()
        self.out = []

    def write(self, data):
        for ch in data.decode():
            line = self.reader.feed(ch)
            if line is not None:
                reply = fw.handle_line(self.leds, line)
                if reply is not None:
                    self.out.append(reply.encode() + b"\n")
        return len(data)

    def readline(self):
        if self.out:
            return self.out.pop(0)
        time.sleep(0.002)
        return b""

    def reset_input_buffer(self):
        self.out.clear()

    def close(self):
        pass


def test_led_controller_drives_this_firmware(leds, monkeypatch):
    monkeypatch.setattr(led_controller, "find_port", lambda pattern: "/dev/ttyACM0")
    monkeypatch.setattr(led_controller, "_open_port", lambda port: SerialToFirmware(leds))
    led = LedController({"reply_timeout_s": 0.2, "brightness": 40})
    try:
        assert led.start() == {"ok": True, "fw": "checkmate-led 1.0"}
        assert led.show([{"sq": "e7", "role": "engine_from"}, {"sq": "e5", "role": "engine_to"}]) == {"ok": True}
        assert lit(leds) == {"e7": scaled((0, 0, 255), 40), "e5": scaled((0, 255, 0), 40)}
        assert led.set_brightness(20) == {"ok": True}
        assert lit(leds)["e7"] == scaled((0, 0, 255), 20)
        assert led.self_test() == {"ok": True}
        assert led.clear() == {"ok": True}
        assert lit(leds) == {}
    finally:
        led.close()
