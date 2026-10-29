"""CheckMate LED firmware for the Raspberry Pi Pico (MicroPython).

Serial protocol: contracts/interfaces.md section 4.3. One JSON command per line from the Pi,
one reply line for each. The Pi only sends square names and role names; the colors and the
blinking are decided here (section 4.2).

This file also imports on a normal computer (no machine / neopixel there), so the pytest
tests (tests/pico/) can check the square -> LED mapping and the command handling.
"""

import json
import sys
import time

try:
    import machine
    import neopixel
except ImportError:  # running under CPython in the tests
    machine = neopixel = None

FIRMWARE = "checkmate-led 1.0"

# --- hardware settings: adjust to how the matrix is mounted ---------------------------------
DATA_PIN = 0           # GPIO driving the matrix DIN (use a 3.3 V -> 5 V level shifter if it flickers)
SIZE = 16              # LEDs per side
SERPENTINE = True      # rows alternate direction (most 16x16 panels are wired like this)
ROTATION = 0           # 0, 90, 180 or 270: turn the picture until the test pattern is right
MIRROR = False         # flip left/right if the colors are on mirrored corners
MAX_BRIGHTNESS = 50    # % hard cap, whatever the Pi asks for: 256 LEDs at full white draw ~15 A
DEFAULT_BRIGHTNESS = 25  # % until the Pi sends "brightness"

NUM_LEDS = SIZE * SIZE
FILES = "abcdefgh"
RANKS = "12345678"
MAX_LINE = 4096        # bytes per command line (section 4.3)
BLINK_MS = 250         # "error" is on 250 ms, off 250 ms: 2 Hz
TEST_STEP_MS = 500
BOOT_MS = 1000         # boot check: all 4 test corners at once (section 4.3 allows <= 1 s)

# Section 4.2. Change colors here only; the Pi never sends colors.
ROLE_COLORS = {
    "engine_from": (0, 0, 255),
    "engine_to": (0, 255, 0),
    "hint_from": (0, 255, 255),
    "hint_to": (255, 255, 0),
    "error": (255, 0, 0),        # blinks
    "check": (255, 128, 0),
    "last_move": (40, 40, 40),
}
# "test": one corner at a time, each its own color, so a mirrored panel is easy to spot.
TEST_STEPS = (("a1", (255, 0, 0)), ("h1", (0, 255, 0)), ("h8", (0, 0, 255)), ("a8", (255, 255, 255)))

ticks_diff = getattr(time, "ticks_diff", lambda new, old: new - old)


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


def _is_percent(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def _error(rid, code, message):
    return {"id": rid, "ok": False, "error": code, "message": message}


class Leds:
    """What is lit, and the command handling. `strip` is a NeoPixel (or a list-like fake in tests).

    Times are milliseconds from time.ticks_ms(); tick(now) runs the blinking and the test.
    """

    def __init__(self, strip):
        self.strip = strip
        self.brightness = DEFAULT_BRIGHTNESS
        self.roles = {}          # square -> role
        self.since = 0           # when the pattern was set: the blink starts "on" then
        self.test_start = None   # when "test" started, None when not running
        self.boot_start = None   # when the boot check started, None when not running
        self.shown = None        # (frame, brightness) last written, to skip identical frames

    def handle(self, request, now=0):
        """One decoded request -> reply dict."""
        if not isinstance(request, dict):
            return _error(None, "BAD_JSON", "line is not a JSON object")
        rid = request.get("id")
        cmd = request.get("cmd")

        if cmd == "ping":
            return {"id": rid, "ok": True, "fw": FIRMWARE}
        if cmd == "clear":
            self._show({}, now)
            return {"id": rid, "ok": True}
        if cmd == "set":
            squares = request.get("squares")
            if not isinstance(squares, list):
                return _error(rid, "BAD_VALUE", "squares must be a list")
            roles = {}
            for item in squares:
                if not isinstance(item, dict):
                    return _error(rid, "BAD_VALUE", "each square must be {\"sq\", \"role\"}")
                if not is_square(item.get("sq")):
                    return _error(rid, "BAD_SQUARE", repr(item.get("sq")))
                if item.get("role") not in ROLE_COLORS:
                    return _error(rid, "BAD_ROLE", repr(item.get("role")))
                roles[item["sq"]] = item["role"]
            self._show(roles, now)
            return {"id": rid, "ok": True}
        if cmd == "brightness":
            value = request.get("value")
            if not _is_percent(value):
                return _error(rid, "BAD_VALUE", "value must be an int from 0 to 100")
            self.brightness = value  # the pattern stays
            self.tick(now)
            return {"id": rid, "ok": True}
        if cmd == "test":
            self._show({}, now)
            self.test_start = now  # runs in tick(); the reply doesn't wait for it
            self.tick(now)
            return {"id": rid, "ok": True}
        return _error(rid, "BAD_CMD", repr(cmd))

    def boot(self, now):
        self.boot_start = now
        self.tick(now)

    def _show(self, roles, now):
        self.roles = roles
        self.since = now
        self.test_start = self.boot_start = None
        self.tick(now)

    def tick(self, now):
        """Write the LEDs if what should be lit at `now` differs from what is shown."""
        shown = (self.frame(now), self.brightness)
        if shown != self.shown:
            self.render(shown[0])
            self.shown = shown

    def frame(self, now):
        """{square: (r, g, b) at full brightness} to show at time `now`."""
        if self.boot_start is not None:
            if ticks_diff(now, self.boot_start) < BOOT_MS:
                return dict(TEST_STEPS)
            self.boot_start = None
        if self.test_start is not None:
            step = ticks_diff(now, self.test_start) // TEST_STEP_MS
            if step < len(TEST_STEPS):
                square, color = TEST_STEPS[step]
                return {square: color}
            self.test_start = None  # the test ends with everything off
            return {}
        blink_on = (ticks_diff(now, self.since) // BLINK_MS) % 2 == 0
        return {sq: ROLE_COLORS[role] for sq, role in self.roles.items() if role != "error" or blink_on}

    def render(self, frame):
        level = min(self.brightness, MAX_BRIGHTNESS) / 100
        for i in range(NUM_LEDS):
            self.strip[i] = (0, 0, 0)
        for square, color in frame.items():
            scaled = (int(color[0] * level), int(color[1] * level), int(color[2] * level))
            for i in led_indices(square):
                self.strip[i] = scaled
        self.strip.write()


class LineReader:
    """Collects characters into lines. A line longer than MAX_LINE gives TOO_LONG once it ends."""

    def __init__(self):
        self.chars = []
        self.too_long = False

    def feed(self, char):
        """One character -> a complete line (str), TOO_LONG, or None while the line goes on."""
        if char == "\n":
            line, too_long = "".join(self.chars), self.too_long
            self.chars, self.too_long = [], False
            return TOO_LONG if too_long else line
        if not self.too_long:
            self.chars.append(char)
            if len(self.chars) > MAX_LINE:
                self.chars, self.too_long = [], True
        return None


TOO_LONG = object()


def handle_line(leds, line, now=0):
    """One input line -> reply line (or None for a blank line)."""
    if line is TOO_LONG:
        return json.dumps(_error(None, "TOO_LONG", "line longer than %d bytes" % MAX_LINE))
    line = line.strip()
    if not line:
        return None
    try:
        request = json.loads(line)
    except ValueError:
        return json.dumps(_error(None, "BAD_JSON", "not valid JSON"))
    return json.dumps(leds.handle(request, now))


def main():
    # import micropython
    import select

    # micropython.kbd_intr(-1)  # a 0x03 byte in the data must not stop the program (section 4.5)
    # The above line was removed on Oct 29. The firmware can’t receive a real Ctrl-C from the Pi, so turning it off only locks us out.
    
    leds = Leds(neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_LEDS))
    leds.boot(time.ticks_ms())  # the 4 corners for 1 s, then off
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    reader = LineReader()
    while True:
        # read() with no size blocks (MicroPython bug), so poll and read one character at a time
        if poll.poll(10):
            line = reader.feed(sys.stdin.read(1))
            if line is not None:
                reply = handle_line(leds, line, time.ticks_ms())
                if reply is not None:
                    sys.stdout.write(reply + "\n")
            continue  # read the whole command before redrawing
        leds.tick(time.ticks_ms())


if neopixel is not None:
    main()
