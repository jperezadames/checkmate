"""CheckMate LED and Grove control firmware for the Raspberry Pi Pico (MicroPython).

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

try:
    from matrix import BoardLayout, FILES, RANKS, ROLE_COLORS, TEST_STEPS
except ImportError:  # shared geometry module in the host test suite
    from checkmate.led.matrix import BoardLayout, FILES, RANKS, ROLE_COLORS, TEST_STEPS

FIRMWARE = "checkmate-pico 2.0"

# --- hardware settings: adjust to how the matrix is mounted ---------------------------------
DATA_PIN = 16          # Grove shield D16, LED matrix data
BUTTON_PIN = 20        # Grove shield D20, Grove Button (HIGH when pressed)
ROTARY_PIN = 26        # Grove shield A0, ADC0
BUTTON_ACTIVE = 1
ROTARY_REVERSED = False
DEBOUNCE_MS = 30
PRESS_MODULUS = 2**30
SIZE = 16              # LEDs per side
SERPENTINE = True      # rows alternate direction (most 16x16 panels are wired like this)
ROTATION = 0           # 0, 90, 180 or 270: turn the picture until the test pattern is right
MIRROR = False         # flip left/right if the colors are on mirrored corners
MAX_BRIGHTNESS = 50    # % hard cap, whatever the Pi asks for: 256 LEDs at full white draw ~15 A
DEFAULT_BRIGHTNESS = 25  # % until the Pi sends "brightness"

NUM_LEDS = SIZE * SIZE
MAX_LINE = 4096        # bytes per command line (section 4.3)
BLINK_MS = 250         # "error" is on 250 ms, off 250 ms: 2 Hz
TEST_STEP_MS = 500
BOOT_MS = 1000         # boot check: all 4 test corners at once (section 4.3 allows <= 1 s)

ticks_diff = getattr(time, "ticks_diff", lambda new, old: new - old)


def is_square(name):
    return isinstance(name, str) and len(name) == 2 and name[0] in FILES and name[1] in RANKS


def led_indices(square):
    """The 4 strip indices under a square like "e4"."""
    return BoardLayout(SIZE, SERPENTINE, ROTATION, MIRROR).indices(square)


def _is_percent(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def _error(rid, code, message):
    return {"id": rid, "ok": False, "error": code, "message": message}


class Controls:
    """Continuously sample A0 and debounce D20, retaining presses between USB polls."""

    def __init__(self, adc, button):
        self.adc = adc
        self.button = button
        self.position = adc.read_u16()
        self.raw_button = button.value()
        self.stable_button = self.raw_button
        self.changed_at = 0
        self.presses = 0

    def tick(self, now):
        self.position = (self.position * 3 + self.adc.read_u16()) // 4
        raw = self.button.value()
        if raw != self.raw_button:
            self.raw_button = raw
            self.changed_at = now
        if raw != self.stable_button and ticks_diff(now, self.changed_at) >= DEBOUNCE_MS:
            self.stable_button = raw
            if raw == BUTTON_ACTIVE:
                self.presses = (self.presses + 1) % PRESS_MODULUS

    def snapshot(self):
        position = 65535 - self.position if ROTARY_REVERSED else self.position
        return {"adc": position, "presses": self.presses}


class Leds:
    """What is lit, and the command handling. `strip` is a NeoPixel (or a list-like fake in tests).

    Times are milliseconds from time.ticks_ms(); tick(now) runs the blinking and the test.
    """

    def __init__(self, strip, controls=None):
        self.strip = strip
        self.controls = controls
        self.layout = BoardLayout(SIZE, SERPENTINE, ROTATION, MIRROR)
        self.max_brightness = MAX_BRIGHTNESS
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
        if cmd == "inputs":
            if self.controls is None:
                return _error(rid, "NO_CONTROLS", "A0 and D20 are not initialized")
            reply = {"id": rid, "ok": True}
            reply.update(self.controls.snapshot())
            return reply
        if cmd == "configure":
            size = request.get("size", SIZE)
            rotation = request.get("rotation", ROTATION)
            serpentine = request.get("serpentine", SERPENTINE)
            mirror = request.get("mirror", MIRROR)
            maximum = request.get("max_brightness", MAX_BRIGHTNESS)
            if (type(size) is not int or size != SIZE or type(rotation) is not int
                    or rotation not in (0, 90, 180, 270) or type(serpentine) is not bool
                    or type(mirror) is not bool or not _is_percent(maximum)):
                return _error(rid, "BAD_VALUE", "invalid matrix configuration")
            self.layout = BoardLayout(size, serpentine, rotation, mirror)
            self.max_brightness = min(maximum, MAX_BRIGHTNESS)
            self.shown = None
            self.tick(now)
            return {"id": rid, "ok": True}
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
        level = min(self.brightness, self.max_brightness) / 100
        for i in range(NUM_LEDS):
            self.strip[i] = (0, 0, 0)
        for square, color in frame.items():
            scaled = (int(color[0] * level), int(color[1] * level), int(color[2] * level))
            for i in self.layout.indices(square):
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
    import select

    # Ctrl-C stays on: mpremote stops this program with it before uploading (section 4.5).
    # The Pi only sends json.dumps lines, so a 0x03 byte never comes in the data.
    controls = Controls(machine.ADC(machine.Pin(ROTARY_PIN)),
                        machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN))
    leds = Leds(neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_LEDS), controls)
    leds.boot(time.ticks_ms())  # the 4 corners for 1 s, then off
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    reader = LineReader()
    while True:
        now = time.ticks_ms()
        controls.tick(now)
        leds.tick(now)
        # read() with no size blocks (MicroPython bug), so poll and read one character at a time
        if poll.poll(10):
            line = reader.feed(sys.stdin.read(1))
            if line is not None:
                reply = handle_line(leds, line, time.ticks_ms())
                if reply is not None:
                    sys.stdout.write(reply + "\n")


if neopixel is not None:
    main()
