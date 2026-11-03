"""Game loop (contracts/interfaces.md section 6).

Runs in one background thread inside the FastAPI backend at about 10 Hz, and is the only
thread that calls Camera, GameEngine and LedController (section 5.1). UI commands arrive
through a queue.Queue; `broadcast` gets every `info`, `state` and `toast` message.

The `state` (section 5.3) and what the LEDs show are both worked out from the loop's fields
after every iteration, and only sent when they differ from what was sent last.
"""

import queue
import random
import time
import traceback
from concurrent.futures import Future

import chess

from checkmate.camera import START_FEN, detect_move, occupancy_from_fen
from checkmate.game.commands import check_command

PERIOD_S = 0.1         # about 10 Hz
CAMERA_GRACE_S = 3.0   # CAMERA_NOT_READY for this long -> error phase (a reopened camera needs a moment)
CRASH_PAUSE_S = 1.0    # after a bug in the loop, so its toast doesn't repeat 10 times a second
ELO_MIN, ELO_MAX = 1320, 3190  # section 1.1, until the engine reports its own range

START_OCCUPANCY = occupancy_from_fen(START_FEN)
BOARD_PHASES = ("setup_check", "human_turn", "engine_move_pending")  # where board_problem shows

SETUP_PROBLEM = "The board doesn't match the starting position. Fix the marked squares."
ILLEGAL_PROBLEM = "That's not a legal move. Put the pieces back."
WRONG_MOVE_PROBLEM = "That's not the computer's move. Fix the marked squares."
NOT_CALIBRATED = "The camera isn't calibrated: set up the starting position and press Calibrate."

PIECE_NAMES = {"q": "queen", "r": "rook", "b": "bishop", "n": "knight"}
TERMINATIONS = {
    "CHECKMATE": "Checkmate",
    "STALEMATE": "Stalemate",
    "INSUFFICIENT_MATERIAL": "Insufficient material",
    "THREEFOLD_REPETITION": "Threefold repetition",
    "FIFTY_MOVES": "Fifty-move rule",
    "FIVEFOLD_REPETITION": "Fivefold repetition",
    "SEVENTYFIVE_MOVES": "Seventy-five-move rule",
    "RESIGNATION": "You resigned",
}
WINNERS = {"1-0": "white", "0-1": "black"}


class DebugImageRequest:
    """For /api/camera.jpg: the server puts one on the command queue and waits for `reply`, so
    camera.get_debug_image() is called from the loop thread like every other module call."""

    def __init__(self):
        self.reply = Future()


def run_game_loop(camera, engine, led, commands, broadcast, stop_event):
    """Start the modules, run until `stop_event` is set, then close them."""
    game = GameLoop(camera, engine, led, broadcast)
    try:
        game.start()
        while not stop_event.is_set():
            began = time.monotonic()
            try:
                game.step(commands)
            except Exception as e:  # a bug here must not stop the game for good
                traceback.print_exc()
                broadcast(_toast("error", f"Internal error: {e}"))
                stop_event.wait(CRASH_PAUSE_S)
            stop_event.wait(max(0.0, PERIOD_S - (time.monotonic() - began)))
    finally:
        game.close()


class GameLoop:
    """The phases of section 6. step() is one iteration; tests call it directly."""

    def __init__(self, camera, engine, led, broadcast, clock=time.monotonic):
        self.camera, self.engine, self.led = camera, engine, led
        self.broadcast = broadcast
        self.clock = clock
        self.phase = "idle"
        self.game = None             # last engine.state() / push_move()["state"]; None = no game
        self.problems = {}           # "camera" / "engine" -> text, while that device has failed
        self.resume = "idle"         # phase to go back to once the problems are fixed
        self.calibrated = True
        self.camera_down_since = None
        self.sent_state = None
        self.sent_leds = None
        self._new_game_fields()

    def _new_game_fields(self):
        self.engine_move = None      # get_engine_move() result, for engine_move_pending
        self.promotion = None        # {"from", "to", "choices"}, for promotion_choice
        self.hint = None
        self.rating = None
        self.evaluation = None
        self.board_problem = None
        self.last_occupancy = None   # last stable occupancy processed

    # -- lifecycle ----------------------------------------------------------------------------

    def start(self):
        res = self.engine.start()
        self._send_info(res if res["ok"] else None)
        if not res["ok"]:
            self._fail("engine", res, resume="idle")
        self.led.start()  # LED_DISCONNECTED: it keeps retrying in the background (section 4.1)
        res = self.camera.start()
        if not res["ok"]:
            self._fail("camera", res, resume="idle")
        else:
            self.calibrated = res["calibrated"]
        self.publish()

    def close(self):
        for close in (self.led.clear, self.led.close, self.camera.close, self.engine.close):
            try:
                close()
            except Exception:
                traceback.print_exc()

    def step(self, commands):
        """Handle the queued commands, do the current phase's work, publish what changed."""
        while True:
            try:
                item = commands.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, DebugImageRequest):
                item.reply.set_result(self.camera.get_debug_image())
            else:
                self.handle(item)
        PHASE_STEPS.get(self.phase, GameLoop._wait)(self)
        self.publish()

    # -- commands (sections 5.4, 5.5) -----------------------------------------------------------

    def handle(self, cmd):
        problem = check_command(cmd, self.phase)  # the phase may have changed since the server checked
        if problem:
            self.toast("error", problem["message"])
            return
        getattr(self, "_cmd_" + cmd["type"])(cmd)

    def _cmd_start_game(self, cmd):
        color = cmd["human_color"]
        if color == "random":
            color = random.choice(("white", "black"))
        res = self.engine.new_game(color, cmd["elo"], cmd["mode"])
        if not res["ok"]:
            self._fail("engine", res, resume="idle")
            return
        self.game = res
        self._new_game_fields()
        self.phase = "setup_check"

    def _cmd_hint(self, cmd):
        res = self.engine.get_hint()
        if not res["ok"]:
            self._fail("engine", res, resume="human_turn")
            return
        self.hint = _fields(res)

    def _cmd_promote(self, cmd):
        self._play(self.promotion["from"] + self.promotion["to"] + cmd["piece"])

    def _cmd_resign(self, cmd):
        res = self.engine.resign(self.game["human_color"])
        if not res["ok"]:
            self.toast("error", res["message"])
            return
        self.game = res
        self.engine_move = self.promotion = self.hint = self.board_problem = None
        self.phase = "game_over"

    def _cmd_cancel(self, cmd):
        self.game = None
        self._new_game_fields()
        self.phase = "idle"

    def _cmd_calibrate(self, cmd):
        came_from = self.phase
        self.phase = "calibrating"
        self.publish()  # calibrate() blocks for up to 5 s
        res = self.camera.calibrate()
        self.phase = came_from
        if res["ok"]:
            self.calibrated = True
            self.camera_down_since = None
            self.problems.pop("camera", None)
            self.toast("info", "Camera calibrated")
            if self.phase == "error" and not self.problems:
                self.phase = self.resume
        elif res["error"] == "CAMERA_NOT_READY":
            self._fail("camera", res, resume="idle")  # from error, the old resume phase stays
        else:
            self.toast("error", f"Calibration failed: {res['message']}")

    def _cmd_retry(self, cmd):
        if "engine" in self.problems:
            self.engine.close()
            res = self.engine.start()
            if res["ok"]:
                del self.problems["engine"]
                self._send_info(res)
            else:
                self.problems["engine"] = _engine_problem(res)
        if "camera" in self.problems:
            res = self.camera.start()
            if not res["ok"]:
                self.problems["camera"] = _camera_problem(res)
            elif not res["calibrated"]:
                self.calibrated = False
                self.problems["camera"] = NOT_CALIBRATED
            else:
                del self.problems["camera"]
                self.camera_down_since = None
        if not self.problems:
            self.phase = self.resume

    # -- phases (section 6) ---------------------------------------------------------------------

    def _wait(self):
        """idle, calibrating, game_over, error: nothing to do until a command arrives."""

    def _step_setup_check(self):
        occupancy = self._observe()
        if occupancy is None:
            return
        if occupancy != START_OCCUPANCY:
            self._board_problem(_diff(START_OCCUPANCY, occupancy), SETUP_PROBLEM)
            return
        self.board_problem = None
        self.last_occupancy = occupancy
        self.phase = "human_turn" if self.game["human_color"] == "white" else "engine_thinking"

    def _step_human(self):
        """human_turn and promotion_choice: look for the human's move."""
        occupancy = self._new_occupancy()
        if occupancy is None:
            return
        res = detect_move(self.game["fen"], occupancy)
        status = res.get("status")
        if status == "move":
            self._play(res["move"])
        elif status == "promotion":
            choices = [uci[4] for uci in res["candidates"]]
            self.promotion = {"from": res["from"], "to": res["to"], "choices": choices}
            self.board_problem = None
            self.phase = "promotion_choice"
        elif status == "no_change":  # e.g. the human put the pieces back
            self.promotion = self.board_problem = None
            self.phase = "human_turn"
        elif status == "invalid":
            self.promotion = None
            self.phase = "human_turn"
            self._board_problem(res["changed_squares"], ILLEGAL_PROBLEM)

    def _step_engine_thinking(self):
        res = self.engine.get_engine_move()  # blocks about think_time_s
        if res["ok"]:
            self.engine_move = _fields(res)
            self.board_problem = None
            self.phase = "engine_move_pending"
        elif res["error"] == "GAME_OVER":
            self.phase = "game_over"
        else:
            self._fail("engine", res, resume="engine_thinking")

    def _step_engine_move_pending(self):
        occupancy = self._new_occupancy()
        if occupancy is None:
            return
        move = self.engine_move["move"]
        res = detect_move(self.game["fen"], occupancy)
        status = res.get("status")
        if (status == "move" and res["move"] == move) or (status == "promotion" and move in res["candidates"]):
            self._play(move)
        elif status == "no_change":  # not played yet, or put back
            self.board_problem = None
        elif res["ok"]:
            board = chess.Board(self.game["fen"])
            board.push_uci(move)
            self._board_problem(_diff(occupancy_from_fen(board.fen()), occupancy), WRONG_MOVE_PROBLEM)

    def _play(self, uci):
        """A move seen on the board (human's, or the computer's once played): push and rate it."""
        res = self.engine.push_move(uci)
        if not res["ok"]:  # detect_move only returns legal moves, so this is a bug
            self.toast("error", f"Move {uci} not accepted: {res['message']}")
            return
        self.game = res["state"]
        self.engine_move = self.promotion = self.hint = self.board_problem = None
        self.rating = self.evaluation = None
        if self.game["game_over"]:
            self.phase = "game_over"
        elif self.game["turn"] == self.game["human_color"]:
            self.phase = "human_turn"
        else:
            self.phase = "engine_thinking"
        self.publish()  # the new position without the old analysis (5.3.1); rating takes ~2 s

        rating = self.engine.rate_last_move()
        if rating["ok"]:
            self.rating = _fields(rating)
            self.evaluation = {"fen": self.game["fen"], "score_cp": rating["score_after"],
                               "mate_in": rating["mate_in"]}
        else:
            self.toast("warning", f"Move analysis unavailable: {rating['message']}")

    # -- helpers --------------------------------------------------------------------------------

    def _observe(self):
        """The occupancy of a stable observation, or None. CAMERA_NOT_READY for longer than
        CAMERA_GRACE_S switches to the error phase."""
        obs = self.camera.get_observation()
        if not obs["ok"]:
            now = self.clock()
            if self.camera_down_since is None:
                self.camera_down_since = now
            elif now - self.camera_down_since >= CAMERA_GRACE_S:
                self._fail("camera", obs, resume=self.phase)
            return None
        self.camera_down_since = None
        return obs["occupancy"] if obs["stable"] else None

    def _new_occupancy(self):
        """A stable occupancy that differs from the last one processed, or None."""
        occupancy = self._observe()
        if occupancy is None or occupancy == self.last_occupancy:
            return None
        self.last_occupancy = occupancy
        return occupancy

    def _board_problem(self, squares, text):
        self.board_problem = {"squares": squares, "text": text}

    def _fail(self, device, res, resume):
        """CAMERA_NOT_READY / ENGINE_ERROR (or any engine error): go to the error phase."""
        self.problems[device] = _camera_problem(res) if device == "camera" else _engine_problem(res)
        if self.phase != "error":
            self.resume = resume
        self.phase = "error"

    def _send_info(self, started):
        """`info` (section 5.2) from engine.start(), or the contract's defaults if it failed."""
        started = started or {"elo_min": ELO_MIN, "elo_max": ELO_MAX, "engine_name": None}
        self.broadcast({"type": "info", "version": "1", "elo_min": started["elo_min"],
                        "elo_max": started["elo_max"], "engine_name": started["engine_name"]})

    def toast(self, level, text):
        self.broadcast(_toast(level, text))

    # -- what is sent ---------------------------------------------------------------------------

    def publish(self):
        leds = self.leds()
        if leds != self.sent_leds:
            # LED_DISCONNECTED is fine: the controller shows the last pattern once it reconnects.
            if leds:
                self.led.show(leds)
            else:
                self.led.clear()
            self.sent_leds = leds
        state = self.state()
        if state != self.sent_state:
            self.broadcast(state)
            self.sent_state = state

    def leds(self) -> list:
        """What the LEDs should show now. One role per square: errors first, then the rest."""
        roles = {}
        if self.phase in BOARD_PHASES and self.board_problem:
            for square in self.board_problem["squares"]:
                roles.setdefault(square, "error")
        if self.phase == "engine_move_pending":
            for item in engine_move_squares(self.engine_move):
                roles.setdefault(item["sq"], item["role"])
        if self.phase == "human_turn":
            if self.hint:
                roles.setdefault(self.hint["from"], "hint_from")
                roles.setdefault(self.hint["to"], "hint_to")
            if self.game["check_square"]:
                roles.setdefault(self.game["check_square"], "check")
        return [{"sq": square, "role": role} for square, role in roles.items()]

    def state(self) -> dict:
        """The `state` message (section 5.3)."""
        game = self.game or {}
        return {
            "type": "state",
            "phase": self.phase,
            "mode": game.get("mode"),
            "fen": game.get("fen"),
            "human_color": game.get("human_color"),
            "turn": game.get("turn"),
            "elo": game.get("elo"),
            "moves_san": game.get("moves_san", []),
            "last_move": game.get("last_move"),
            "in_check": game.get("in_check", False),
            "engine_move": self.engine_move if self.phase == "engine_move_pending" else None,
            "promotion": self.promotion if self.phase == "promotion_choice" else None,
            "hint": self.hint,
            "rating": self.rating,
            "evaluation": self.evaluation,
            "board_problem": self.board_problem if self.phase in BOARD_PHASES else None,
            "result": game.get("result"),
            "termination": game.get("termination"),
            "message": self.message(),
            "devices": {
                "camera": "error" if "camera" in self.problems or not self.calibrated else "ok",
                "engine": "error" if "engine" in self.problems else "ok",
                "led": "ok" if self.led.is_connected() else "error",
            },
        }

    def message(self) -> str:
        phase = self.phase
        if phase in BOARD_PHASES and self.board_problem:
            return self.board_problem["text"]
        if phase == "idle":
            return "Choose your color and difficulty." if self.calibrated else NOT_CALIBRATED
        if phase == "calibrating":
            return "Calibrating the camera: keep the pieces in the starting position."
        if phase == "setup_check":
            return "Set up the pieces in the starting position."
        if phase == "human_turn":
            text = "Check! Your move." if self.game["in_check"] else "Your move."
            if self.hint:
                text += f" Hint: {self.hint['san']} ({self.hint['from']}→{self.hint['to']})"
            return text
        if phase == "engine_thinking":
            return "The computer is thinking…"
        if phase == "engine_move_pending":
            return describe_engine_move(self.engine_move)
        if phase == "promotion_choice":
            return "Which piece did you promote to?"
        if phase == "game_over":
            how = TERMINATIONS.get(self.game["termination"], "Game over")
            winner = WINNERS.get(self.game["result"])
            if winner is None:
                return f"{how}. It's a draw."
            return f"{how}. " + ("You win!" if winner == self.game["human_color"] else "The computer wins.")
        return " ".join(self.problems.values())  # error


PHASE_STEPS = {
    "setup_check": GameLoop._step_setup_check,
    "human_turn": GameLoop._step_human,
    "promotion_choice": GameLoop._step_human,
    "engine_thinking": GameLoop._step_engine_thinking,
    "engine_move_pending": GameLoop._step_engine_move_pending,
}


def engine_move_squares(move: dict) -> list:
    """LED squares for the computer's move (table in section 4.2)."""
    sources, targets = [move["from"]], [move["to"]]
    if move["rook_from"]:  # castling
        sources.append(move["rook_from"])
        targets.append(move["rook_to"])
    if move["capture_square"] and move["capture_square"] != move["to"]:  # en passant
        sources.append(move["capture_square"])
    return [{"sq": sq, "role": "engine_from"} for sq in sources] + \
           [{"sq": sq, "role": "engine_to"} for sq in targets]


def describe_engine_move(move: dict) -> str:
    """e.g. "Play the computer's move: O-O (e1→g1, rook h1→f1)"."""
    text = f"Play the computer's move: {move['san']} ({move['from']}→{move['to']}"
    if move["rook_from"]:
        text += f", rook {move['rook_from']}→{move['rook_to']}"
    if move["capture_square"] and move["capture_square"] != move["to"]:
        text += f", remove the pawn on {move['capture_square']}"
    if move["promotion"]:
        text += f", put a {PIECE_NAMES[move['promotion']]} on {move['to']}"
    return text + ")"


def _fields(res: dict) -> dict:
    """A module result without its "ok", as the state fields carry it."""
    return {key: value for key, value in res.items() if key != "ok"}


def _diff(a: str, b: str) -> list:
    return [chess.square_name(i) for i in range(64) if a[i] != b[i]]


def _camera_problem(res: dict) -> str:
    return f"Camera problem: {res['message'].rstrip('.')}. Check the camera, then press Retry."


def _engine_problem(res: dict) -> str:
    return f"Engine problem: {res['message'].rstrip('.')}. Press Retry to restart it."


def _toast(level: str, text: str) -> dict:
    return {"type": "toast", "level": level, "text": text}
