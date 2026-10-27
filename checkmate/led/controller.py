"""LedController: drives the Pico LED board over USB serial (JSON lines).

Protocol (one JSON object per line, UTF-8, "\\n"-terminated; every request gets one reply with
the same "id"):

    Pi -> Pico                                               Pico -> Pi
    {"id": 1, "cmd": "ping"}                                 {"id": 1, "ok": true, "fw": "checkmate-led 1"}
    {"id": 2, "cmd": "show", "brightness": 0.25,
     "squares": {"e2": [0, 255, 0], "e4": [0, 90, 255]}}     {"id": 2, "ok": true}
    {"id": 3, "cmd": "test"}                                 {"id": 3, "ok": true}
    errors:                                                  {"id": n, "ok": false, "error": "BAD_REQUEST",
                                                              "message": "..."}

"show" replaces the whole board (squares not listed go dark), so it is safe to resend after a
reconnect. "test" lights a1 red, h1 green, h8 blue and a8 white, for checking the wiring.

Public methods never raise; they return {"ok": True, ...} or err(CODE, message) (section 1.5).
If the Pico is unplugged, calls return LED_NOT_READY and the next call reconnects and puts the
last frame back.
"""

import json
import threading
import time

from checkmate.errors import err
from checkmate.led.frames import check_frame, frame_colors, move_frame

# USB vendor id of the Raspberry Pi Pico (MicroPython USB serial).
PICO_USB_VID = 0x2E8A

# Read timeout for one serial readline(); the whole reply wait is timeout_s.
READ_POLL_S = 0.05


def _open_port(port, baudrate):
    """Open a serial port. Separate function so tests can replace it."""
    import serial  # pyserial

    return serial.Serial(port, baudrate=baudrate, timeout=READ_POLL_S, write_timeout=1.0)


def find_pico_port():
    """Device path of the first Raspberry Pi Pico on USB, or None."""
    from serial.tools import list_ports

    for info in list_ports.comports():
        if info.vid == PICO_USB_VID:
            return info.device
    return None


class _LinkError(Exception):
    pass


class LedController:
    def __init__(self, config: dict):
        self.port = config.get("port", "auto")
        self.baudrate = int(config.get("baudrate", 115200))
        self.timeout_s = float(config.get("timeout_s", 1.0))
        self.brightness = float(config.get("brightness", 0.25))
        if not 0.0 <= self.brightness <= 1.0:
            raise ValueError(f"led.brightness must be between 0 and 1, got {self.brightness}")

        self._lock = threading.Lock()
        self._serial = None
        self._next_id = 0
        self._wanted = {}   # frame the board should show
        self._shown = None  # frame the Pico confirmed (None = unknown)
        self.port_name = None
        self.firmware = None

    @property
    def connected(self) -> bool:
        return self._serial is not None

    # -- lifecycle --------------------------------------------------------

    def start(self) -> dict:
        """Connect (or reconnect) to the Pico and restore the current frame."""
        with self._lock:
            if self._serial is not None:
                try:
                    self._exchange({"cmd": "ping"})
                    return self._started()
                except Exception:
                    self._close_serial()
            problem = self._connect()
            return problem or self._started()

    def _started(self):
        return {"ok": True, "port": self.port_name, "firmware": self.firmware}

    def close(self) -> None:
        """Turn the LEDs off (if connected) and release the port."""
        with self._lock:
            if self._serial is not None:
                try:
                    self._exchange({"cmd": "show", "squares": {}, "brightness": self.brightness})
                except Exception:
                    pass
            self._close_serial()

    # -- what to show -----------------------------------------------------

    def show(self, frame: dict) -> dict:
        """Show {square: role}; every other square goes dark. Roles: see frames.ROLE_COLORS."""
        problem = check_frame(frame)
        if problem:
            return err("BAD_REQUEST", problem)
        with self._lock:
            self._wanted = dict(frame)
            if self._serial is not None and self._shown == self._wanted:
                return {"ok": True}  # already showing it; the game loop can call this every tick
            return self._call(self._show_request())

    def show_move(self, move: dict) -> dict:
        """Light a move dict (state.engine_move): from, to, castling rook, en passant capture."""
        if not isinstance(move, dict) or not move.get("from") or not move.get("to"):
            return err("BAD_REQUEST", "move must be a dict with 'from' and 'to'")
        return self.show(move_frame(move))

    def show_hint(self, move: dict) -> dict:
        if not isinstance(move, dict) or not move.get("from") or not move.get("to"):
            return err("BAD_REQUEST", "move must be a dict with 'from' and 'to'")
        return self.show(move_frame(move, "hint", "hint"))

    def show_problem(self, squares) -> dict:
        """Light the squares that don't match the expected position (state.board_problem)."""
        if not isinstance(squares, (list, tuple)):
            return err("BAD_REQUEST", "squares must be a list of square names")
        return self.show({square: "problem" for square in squares})

    def clear(self) -> dict:
        return self.show({})

    def test_pattern(self) -> dict:
        """a1 red, h1 green, h8 blue, a8 white: for checking ROTATION / MIRROR in pico/main.py."""
        with self._lock:
            self._shown = None  # the next show() must be sent again
            return self._call({"cmd": "test"})

    # -- serial link (call with the lock held) -----------------------------

    def _show_request(self):
        return {"cmd": "show", "squares": frame_colors(self._wanted), "brightness": self.brightness}

    def _call(self, request) -> dict:
        if self._serial is None:
            problem = self._connect()
            if problem:
                return problem
            if request.get("cmd") == "show":
                return {"ok": True}  # _connect() already sent the wanted frame
        try:
            reply = self._exchange(request)
        except Exception as e:
            self._close_serial()
            return err("LED_NOT_READY", f"lost the Pico: {e}")
        if not reply.get("ok"):
            return err(str(reply.get("error", "LED_ERROR")), str(reply.get("message", "")))
        if request.get("cmd") == "show":
            self._shown = dict(self._wanted)
        return {"ok": True}

    def _connect(self):
        """Open the port, ping the Pico and send the wanted frame. Returns None or an err dict."""
        self._close_serial()
        try:
            port = find_pico_port() if self.port == "auto" else self.port
        except Exception as e:
            return err("LED_NOT_READY", f"cannot list serial ports: {e}")
        if port is None:
            return err("LED_NOT_READY", "no Raspberry Pi Pico found on USB; set led.port in config.json")
        try:
            self._serial = _open_port(port, self.baudrate)
            self._serial.reset_input_buffer()
            self._serial.write(b"\n")  # end any half-written line from before
            pong = self._exchange({"cmd": "ping"})
            reply = self._exchange(self._show_request())
            if not reply.get("ok"):
                raise _LinkError(reply.get("message", "show failed"))
        except Exception as e:
            self._close_serial()
            return err("LED_NOT_READY", f"cannot talk to the Pico on {port}: {e}")
        self.port_name = port
        self.firmware = pong.get("fw")
        self._shown = dict(self._wanted)
        return None

    def _exchange(self, request) -> dict:
        """Send one request and wait for the reply with the same id. Raises on failure."""
        self._next_id += 1
        rid = self._next_id
        line = json.dumps(dict(request, id=rid), separators=(",", ":")) + "\n"
        self._serial.write(line.encode("utf-8"))
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            try:
                reply = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue  # REPL banner or other text from the Pico
            if isinstance(reply, dict) and reply.get("id") == rid:
                return reply
        raise _LinkError(f"no reply within {self.timeout_s:g} s (is pico/main.py on the Pico?)")

    def _close_serial(self):
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._shown = None
