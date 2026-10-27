"""FakeLedController: same methods as LedController, no hardware. Prints an 8x8 text grid."""

from checkmate.errors import err
from checkmate.led.frames import check_frame, move_frame, render_grid


class FakeLedController:
    """Tests can read `frame` / `history`, and set `fail = True` to simulate an unplugged Pico."""

    def __init__(self, config: dict = None, echo: bool = True):
        config = config or {}
        self.echo = config.get("echo", echo)
        self.frame = {}
        self.history = []  # every frame shown, in order (repeats are not recorded)
        self.fail = False
        self.started = False

    @property
    def connected(self) -> bool:
        return self.started and not self.fail

    def start(self) -> dict:
        if self.fail:
            return err("LED_NOT_READY", "fake LED board set to fail")
        self.started = True
        return {"ok": True, "port": "fake", "firmware": "fake"}

    def close(self) -> None:
        self.frame = {}
        self.started = False

    def show(self, frame: dict) -> dict:
        problem = check_frame(frame)
        if problem:
            return err("BAD_REQUEST", problem)
        if self.fail:
            return err("LED_NOT_READY", "fake LED board set to fail")
        self.started = True  # like the real one, connects on first use
        if frame != self.frame:
            self.frame = dict(frame)
            self.history.append(dict(frame))
            if self.echo:
                print("LEDs:\n" + render_grid(self.frame), flush=True)
        return {"ok": True}

    def show_move(self, move: dict) -> dict:
        if not isinstance(move, dict) or not move.get("from") or not move.get("to"):
            return err("BAD_REQUEST", "move must be a dict with 'from' and 'to'")
        return self.show(move_frame(move))

    def show_hint(self, move: dict) -> dict:
        if not isinstance(move, dict) or not move.get("from") or not move.get("to"):
            return err("BAD_REQUEST", "move must be a dict with 'from' and 'to'")
        return self.show(move_frame(move, "hint", "hint"))

    def show_problem(self, squares) -> dict:
        if not isinstance(squares, (list, tuple)):
            return err("BAD_REQUEST", "squares must be a list of square names")
        return self.show({square: "problem" for square in squares})

    def clear(self) -> dict:
        return self.show({})

    def test_pattern(self) -> dict:
        if self.fail:
            return err("LED_NOT_READY", "fake LED board set to fail")
        return self.show({"a1": "capture", "h1": "from", "h8": "to", "a8": "hint"})
