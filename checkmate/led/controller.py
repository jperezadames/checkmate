"""LedController: the Pi side of the LED board (contracts/interfaces.md sections 4.1, 4.3).

Talks to pico/main.py over USB serial, one JSON object per line. The Pi sends one command at a
time and waits for the reply with the same id. No reply within reply_timeout_s: resend once
with the same id; still nothing: the link is down and the call returns LED_DISCONNECTED.

While the link is down, a background thread pings every 2 s, reopening the port. When the Pico
answers, it gets the brightness and the last pattern again, so main never has to resend.

Public methods never raise and return within about 1.2 s (section 4.1).
"""

import glob
import json
import os
import threading
import time

from checkmate.errors import err
from checkmate.led.squares import check_squares

FALLBACK_PORT = "/dev/ttyACM0"
BAUDRATE = 115200        # ignored by USB CDC, but pyserial needs one (section 4.3)
PING_INTERVAL_S = 2.0    # while disconnected
READ_POLL_S = 0.05       # one serial readline(); the whole wait is reply_timeout_s
LOCK_WAIT_S = 0.2        # main gives up this soon while the background thread reconnects


def _open_port(port):
    """Open a serial port. Separate function so tests can replace it."""
    import serial  # pyserial

    return serial.Serial(port, baudrate=BAUDRATE, timeout=READ_POLL_S, write_timeout=0.5)


def find_port(pattern: str):
    """First device matching `pattern` (a path or a glob), else /dev/ttyACM0 if present, else None."""
    matches = sorted(glob.glob(pattern))
    if matches:
        return matches[0]
    return FALLBACK_PORT if os.path.exists(FALLBACK_PORT) else None


class _LinkDown(Exception):
    """The Pico is unplugged or not answering."""


class LedController:
    def __init__(self, config: dict):
        brightness = config.get("brightness", 40)
        if isinstance(brightness, bool) or not isinstance(brightness, int) or not 0 <= brightness <= 100:
            raise ValueError(f"led.brightness must be an int from 0 to 100, got {brightness!r}")
        self._port_pattern = config.get("port", FALLBACK_PORT)
        self._reply_timeout = float(config.get("reply_timeout_s", 0.5))

        # What main asked for last; sent again after every (re)connect.
        self._brightness = brightness
        self._squares = []

        self._lock = threading.Lock()  # the port is shared with the reconnect thread
        self._stop = threading.Event()
        self._thread = None
        self._serial = None
        self._rx = b""                 # part of a reply line read so far
        self._next_id = 0
        self._connected = False
        self._fw = None
        self._why = "not connected yet"  # last link problem, for LED_DISCONNECTED messages

    # -- lifecycle -----------------------------------------------------------------------------

    def start(self) -> dict:
        """Open the port and ping the Pico. If that fails, keep retrying in the background."""
        with self._lock:
            if not self._connected:
                self._try_connect()
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._reconnect_loop, name="led", daemon=True)
            self._thread.start()
        if self._connected:
            return {"ok": True, "fw": self._fw}
        return err("LED_DISCONNECTED", self._why)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        with self._lock:
            self._drop("closed")

    # -- section 4.1 ---------------------------------------------------------------------------

    def show(self, squares: list) -> dict:
        """Replace everything lit with `squares`: [{"sq": "e7", "role": "engine_from"}, ...]."""
        problem = check_squares(squares)
        if problem:
            return err("BAD_REQUEST", problem)
        self._squares = [{"sq": item["sq"], "role": item["role"]} for item in squares]
        return self._send({"cmd": "set", "squares": self._squares})

    def clear(self) -> dict:
        self._squares = []
        return self._send({"cmd": "clear"})

    def set_brightness(self, percent: int) -> dict:
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
            return err("BAD_REQUEST", f"brightness must be an int from 0 to 100, got {percent!r}")
        self._brightness = percent
        return self._send({"cmd": "brightness", "value": percent})

    def self_test(self) -> dict:
        """a1, h1, h8, a8 one by one, then off: checks the board's orientation."""
        self._squares = []  # the test ends with everything off
        return self._send({"cmd": "test"})

    def is_connected(self) -> bool:
        return self._connected

    # -- one command from main -----------------------------------------------------------------

    def _send(self, cmd: dict) -> dict:
        if self._thread is None:
            return err("NOT_STARTED", "start() was not called")
        # The pattern and brightness are already remembered, so if the link is down the
        # reconnect thread shows them as soon as the Pico answers again.
        if not self._lock.acquire(timeout=LOCK_WAIT_S):
            return err("LED_DISCONNECTED", "reconnecting to the Pico")
        try:
            if not self._connected:
                return err("LED_DISCONNECTED", self._why)
            reply = self._command(cmd)
        except _LinkDown as e:
            return err("LED_DISCONNECTED", str(e))
        finally:
            self._lock.release()
        if not reply.get("ok"):
            return err("LED_REJECTED", f"{reply.get('error')}: {reply.get('message')}")
        return {"ok": True}

    # -- the link (call with the lock held) ------------------------------------------------------

    def _reconnect_loop(self):
        while not self._stop.wait(PING_INTERVAL_S):
            if self._connected:
                continue
            with self._lock:
                if not self._connected and not self._stop.is_set():
                    self._try_connect()

    def _try_connect(self) -> bool:
        try:
            self._connect()
            return True
        except Exception as e:  # _LinkDown, or the port could not be opened
            self._drop(str(e))
            return False

    def _connect(self):
        """Reopen the port, ping the Pico, then send the brightness and the pattern."""
        self._drop(self._why)
        port = find_port(self._port_pattern)
        if port is None:
            raise _LinkDown(f"no Pico at {self._port_pattern} or {FALLBACK_PORT}")
        self._serial = _open_port(port)
        self._serial.reset_input_buffer()
        self._serial.write(b"\n")  # end a half-written line left by an earlier run
        self._fw = self._command({"cmd": "ping"}).get("fw")
        # Main may change the pattern while this runs (it doesn't wait for the lock),
        # so send until what was sent is still what main wants.
        while True:
            brightness, squares = self._brightness, self._squares
            self._command({"cmd": "brightness", "value": brightness})
            self._command({"cmd": "set", "squares": squares})
            if brightness == self._brightness and squares is self._squares:
                return

    def _command(self, cmd: dict) -> dict:
        """Send one command and return the Pico's reply. Raises _LinkDown."""
        if self._serial is None:
            raise _LinkDown(self._why)
        self._next_id = self._next_id % 2**31 + 1
        rid = self._next_id
        line = json.dumps(dict(cmd, id=rid), separators=(",", ":")).encode() + b"\n"
        for _ in range(2):  # resend once with the same id (section 4.3)
            try:
                self._serial.write(line)
                reply = self._read_reply(rid)
            except Exception as e:  # unplugged: the port itself fails
                self._drop(f"serial port error: {e}")
                raise _LinkDown(self._why) from e
            if reply is not None:
                self._connected = True
                return reply
        self._drop(f"no reply from the Pico within {self._reply_timeout:g} s")
        raise _LinkDown(self._why)

    def _read_reply(self, rid: int):
        deadline = time.monotonic() + self._reply_timeout
        while time.monotonic() < deadline:
            self._rx += self._serial.readline()
            if not self._rx.endswith(b"\n"):
                continue
            line, self._rx = self._rx, b""
            try:
                reply = json.loads(line)
            except ValueError:
                continue  # REPL banner or other text from the Pico
            # Other ids are late replies to earlier commands; id null answers a garbled
            # line, which only the "\n" sent on connect can cause.
            if isinstance(reply, dict) and reply.get("id") == rid:
                return reply
        return None

    def _drop(self, why: str):
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._rx = b""
        self._connected = False
        self._why = why
