"""CheckMate LED firmware for the Raspberry Pi Pico (MicroPython).
This file also imports on a normal computer (no machine / neopixel there), so the pytest
tests can check the square -> LED mapping and the command handling.
"""

import json
import sys

try:
    import machine
    import neopixel
except ImportError:  # running under CPython in the tests
    machine = neopixel = None

FIRMWARE = "checkmate-led 1"

# --- hardware settings: adjust to how the matrix is mounted ---------------------------------
DATA_PIN = 0           # GPIO driving the matrix DIN (use a 3.3 V -> 5 V level shifter if it flickers)
SIZE = 16              # LEDs per side
SERPENTINE = True      # rows alternate direction (most 16x16 panels are wired like this)
ROTATION = 0           # 0, 90, 180 or 270: turn the picture until the test pattern is right
MIRROR = False         # flip left/right if the colors are on mirrored corners
MAX_BRIGHTNESS = 0.5   # hard cap, whatever the Pi asks for: 256 LEDs at full white draw ~15 A
DEFAULT_BRIGHTNESS = 0.25

NUM_LEDS = SIZE * SIZE
FILES = "abcdefgh"
RANKS = "12345678"
TEST_PATTERN = {"a1": (255, 0, 0), "h1": (0, 255, 0), "h8": (0, 0, 255), "a8": (255, 255, 255)}


def _physical_index(x, y):
    """Logical LED (x from the a-file side, y from the rank-1 side) -> index on the strip.

    Index 0 is assumed to be at the a1 corner with the first row running along rank 1;
    ROTATION / MIRROR cover the other ways the panel can be mounted.
    """
    for _ in range((ROTATION // 90) % 4):
        x, y = y, SIZE - 1 - x
    if MIRROR:
        x = SIZE - 1 - x
    if SERPENTINE and y % 2 == 1:
        x = SIZE - 1 - x
    return y * SIZE + x


def is_square(name):
    return isinstance(name, str) and len(name) == 2 and name[0] in FILES and name[1] in RANKS


def led_indices(square):
    """The 4 strip indices under a square like "e4"."""
    f = FILES.index(square[0])
    r = RANKS.index(square[1])
    x, y = 2 * f, 2 * r
    return [_physical_index(x + dx, y + dy) for dy in (0, 1) for dx in (0, 1)]


def _is_color(value):
    return (isinstance(value, (list, tuple)) and len(value) == 3
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value))


def _error(rid, code, message):
    return {"id": rid, "ok": False, "error": code, "message": message}


class Leds:
    """Board state + command handling. `strip` is a NeoPixel (or a list-like fake in tests)."""

    def __init__(self, strip):
        self.strip = strip
        self.brightness = DEFAULT_BRIGHTNESS
        self.colors = {}  # square -> (r, g, b) at full brightness

    def render(self):
        level = min(max(self.brightness, 0.0), MAX_BRIGHTNESS)
        for i in range(NUM_LEDS):
            self.strip[i] = (0, 0, 0)
        for square, color in self.colors.items():
            scaled = (int(color[0] * level), int(color[1] * level), int(color[2] * level))
            for i in led_indices(square):
                self.strip[i] = scaled
        self.strip.write()

    def handle(self, request):
        """One decoded request -> reply dict."""
        if not isinstance(request, dict):
            return _error(None, "BAD_REQUEST", "request must be a JSON object")
        rid = request.get("id")
        cmd = request.get("cmd")

        if cmd == "ping":
            return {"id": rid, "ok": True, "fw": FIRMWARE}

        if cmd == "show":
            squares = request.get("squares", {})
            if not isinstance(squares, dict):
                return _error(rid, "BAD_REQUEST", "squares must be an object")
            colors = {}
            for square, color in squares.items():
                if not is_square(square):
                    return _error(rid, "BAD_REQUEST", "bad square " + repr(square))
                if not _is_color(color):
                    return _error(rid, "BAD_REQUEST", "bad color for " + square)
                colors[square] = tuple(color)
            brightness = request.get("brightness", self.brightness)
            if not isinstance(brightness, (int, float)) or isinstance(brightness, bool) \
                    or not 0 <= brightness <= 1:
                return _error(rid, "BAD_REQUEST", "brightness must be between 0 and 1")
            self.colors = colors
            self.brightness = float(brightness)
            self.render()
            return {"id": rid, "ok": True}

        if cmd == "test":
            self.colors = dict(TEST_PATTERN)
            self.render()
            return {"id": rid, "ok": True}

        return _error(rid, "BAD_REQUEST", "unknown cmd " + repr(cmd))


def handle_line(leds, line):
    """One input line -> reply line (or None for a blank line)."""
    line = line.strip()
    if not line:
        return None
    try:
        request = json.loads(line)
    except ValueError:
        return json.dumps(_error(None, "BAD_REQUEST", "not valid JSON"))
    return json.dumps(leds.handle(request))


def main():
    import time

    leds = Leds(neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_LEDS))
    leds.handle({"cmd": "test"})  # boot check: corners light up for 1 s
    time.sleep(1)
    leds.handle({"cmd": "show", "squares": {}})
    while True:
        reply = handle_line(leds, sys.stdin.readline())
        if reply is not None:
            sys.stdout.write(reply + "\n")


if neopixel is not None:
    main()
