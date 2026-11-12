"""LedController: the Pi drives the WS2812 matrix directly (contracts/interfaces.md section 4).

No Pico. The Pi 5 sends the WS2812 signal over SPI (driver.py), and this module owns what the
old firmware did: the role colours and square -> LED mapping (matrix.py), the 2 Hz "error"
blink, and the self-test / boot corners. A background thread redraws for the blink and reopens
the SPI device if it goes away, so the game keeps running without LEDs (devices.led = "error").

Public methods never raise and return quickly (section 4.1). Errors are returned, not raised:
BAD_REQUEST for a bad argument, LED_DISCONNECTED when the SPI device can't be used.
"""

import threading
import time

from checkmate.errors import err
from checkmate.led.driver import Ws2812Spi, open_spi
from checkmate.led.matrix import ROLE_COLORS, TEST_STEPS, BoardLayout
from checkmate.led.squares import check_squares

FIRMWARE = "checkmate-led-pi 1.0"
TICK_S = 0.05            # render-thread cadence
BLINK_S = 0.25           # "error" on 0.25 s, off 0.25 s -> 2 Hz
TEST_STEP_S = 0.5        # each self-test corner
BOOT_S = 1.0             # all 4 corners at once on start, then off
REOPEN_INTERVAL_S = 2.0  # while the SPI device is unavailable


class LedController:
    def __init__(self, config: dict):
        config = config or {}
        brightness = config.get("brightness", 40)
        if isinstance(brightness, bool) or not isinstance(brightness, int) or not 0 <= brightness <= 100:
            raise ValueError(f"led.brightness must be an int from 0 to 100, got {brightness!r}")
        self._bus = int(config.get("spi_bus", 0))
        self._device = int(config.get("spi_device", 0))
        self._hz = int(config.get("spi_hz", 2_400_000))
        self._max_brightness = int(config.get("max_brightness", 50))  # hard cap, 256 LEDs ~ 15 A
        self._layout = BoardLayout(
            size=int(config.get("size", 16)),
            serpentine=bool(config.get("serpentine", True)),
            rotation=int(config.get("rotation", 0)),
            mirror=bool(config.get("mirror", False)),
        )

        # What should be lit; sent again whenever the SPI device is (re)opened.
        self._brightness = brightness
        self._roles = {}           # square -> role
        self._since = 0.0          # when the pattern was set (blink starts "on" then)
        self._test_start = None
        self._boot_start = None
        self._shown = None         # last (frame, brightness) written, to skip identical frames

        self._lock = threading.RLock()  # the SPI device is shared with the render thread
        self._stop = threading.Event()
        self._thread = None
        self._driver = None
        self._connected = False
        self._why = "not started"
        self._last_reopen = 0.0

    # -- lifecycle (section 4.1) -------------------------------------------------------------

    def start(self) -> dict:
        """Open the SPI device and start the render thread. If the device isn't there, keep
        retrying in the background; the game runs without LEDs."""
        with self._lock:
            self._open()
            if self._connected:
                self._boot_start = self._since = time.monotonic()
                self._tick(self._boot_start)  # show the 4 corners (section 4.3 boot check)
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="led", daemon=True)
            self._thread.start()
        if self._connected:
            return {"ok": True, "fw": FIRMWARE}
        return err("LED_DISCONNECTED", self._why)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        with self._lock:
            if self._connected:
                try:
                    self._driver.write([(0, 0, 0)] * self._layout.num_leds)
                except Exception:
                    pass
            self._drop("closed")

    # -- commands (section 4.1) --------------------------------------------------------------

    def show(self, squares: list) -> dict:
        """Replace everything lit with `squares`: [{"sq": "e7", "role": "engine_from"}, ...]."""
        problem = check_squares(squares)
        if problem:
            return err("BAD_REQUEST", problem)
        with self._lock:
            self._roles = {item["sq"]: item["role"] for item in squares}
            self._test_start = self._boot_start = None
            self._since = time.monotonic()
            return self._apply()

    def clear(self) -> dict:
        with self._lock:
            self._roles = {}
            self._test_start = self._boot_start = None
            return self._apply()

    def set_brightness(self, percent: int) -> dict:
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
            return err("BAD_REQUEST", f"brightness must be an int from 0 to 100, got {percent!r}")
        with self._lock:
            self._brightness = percent  # the pattern stays
            return self._apply()

    def self_test(self) -> dict:
        """a1, h1, h8, a8 one by one, then off: checks the board's orientation."""
        with self._lock:
            self._roles = {}
            self._boot_start = None
            self._test_start = time.monotonic()
            return self._apply()

    def is_connected(self) -> bool:
        return self._connected

    # -- rendering ---------------------------------------------------------------------------

    def _apply(self) -> dict:
        """Render the current state now and report whether the board is connected."""
        if not self._connected:
            return err("LED_DISCONNECTED", self._why)
        self._tick(time.monotonic())
        if not self._connected:  # a write during the tick may have failed
            return err("LED_DISCONNECTED", self._why)
        return {"ok": True}

    def _run(self):
        """Redraw for the blink / test animation, and reopen the SPI device if it's gone."""
        while not self._stop.wait(TICK_S):
            now = time.monotonic()
            with self._lock:
                if not self._connected:
                    if now - self._last_reopen >= REOPEN_INTERVAL_S:
                        self._last_reopen = now
                        self._open()
                    continue
                self._tick(now)

    def _tick(self, now):
        frame = self._frame(now)
        signature = (tuple(sorted(frame.items())), self._brightness)
        if signature == self._shown:
            return
        self._render(frame)
        self._shown = signature

    def _frame(self, now):
        """{square: (r, g, b) at full brightness} to show at `now`: boot, test, or the pattern."""
        if self._boot_start is not None:
            if now - self._boot_start < BOOT_S:
                return dict(TEST_STEPS)
            self._boot_start = None
        if self._test_start is not None:
            step = int((now - self._test_start) // TEST_STEP_S)
            if step < len(TEST_STEPS):
                square, color = TEST_STEPS[step]
                return {square: color}
            self._test_start = None  # the test ends with everything off
            return {}
        blink_on = int((now - self._since) // BLINK_S) % 2 == 0
        return {sq: ROLE_COLORS[role] for sq, role in self._roles.items()
                if role != "error" or blink_on}

    def _render(self, frame):
        level = min(self._brightness, self._max_brightness) / 100
        pixels = [(0, 0, 0)] * self._layout.num_leds
        for square, color in frame.items():
            scaled = (int(color[0] * level), int(color[1] * level), int(color[2] * level))
            for i in self._layout.indices(square):
                pixels[i] = scaled
        try:
            self._driver.write(pixels)
        except Exception as e:
            self._drop(f"SPI write failed: {e}")

    # -- device ------------------------------------------------------------------------------

    def _open(self):
        self._drop(self._why)
        try:
            spi = open_spi(self._bus, self._device, self._hz)
        except Exception as e:
            self._why = f"could not open SPI {self._bus}.{self._device}: {e}"
            return
        self._driver = Ws2812Spi(spi)
        self._connected = True
        self._shown = None  # force a redraw so the remembered pattern comes back

    def _drop(self, why):
        if self._driver is not None:
            self._driver.close()
        self._driver = None
        self._connected = False
        self._why = why
