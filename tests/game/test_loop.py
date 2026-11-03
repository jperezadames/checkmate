"""The game loop (section 6) with the fake camera and engine, one step() at a time."""

import queue

import chess
import pytest

from checkmate.camera import START_FEN, FakeCamera, occupancy_from_fen
from checkmate.engine import FakeGameEngine
from checkmate.errors import err
from checkmate.game import DebugImageRequest, GameLoop
from checkmate.game.loop import CAMERA_GRACE_S, describe_engine_move, engine_move_squares

START_OCC = occupancy_from_fen(START_FEN)


class ScriptedEngine(FakeGameEngine):
    """Plays the moves in `script` in order, then the first legal move like FakeGameEngine."""

    def __init__(self, script=()):
        super().__init__({})
        self.script = list(script)
        self.starts = 0

    def start(self):
        self.starts += 1
        return super().start()

    def get_engine_move(self):
        if not self.script:
            return super().get_engine_move()
        return self._move_details(chess.Move.from_uci(self.script.pop(0)))


class RecordingLed:
    """LedController stand-in: remembers what is lit; `connected` = False acts unplugged."""

    def __init__(self):
        self.lit = None
        self.connected = True

    def start(self):
        return {"ok": True, "fw": "test"}

    def close(self):
        pass

    def show(self, squares):
        self.lit = {item["sq"]: item["role"] for item in squares}
        return {"ok": True} if self.connected else err("LED_DISCONNECTED", "unplugged")

    def clear(self):
        return self.show([])

    def is_connected(self):
        return self.connected


class Game:
    """A GameLoop with fakes, a fake clock and everything it broadcast."""

    def __init__(self, engine=None, camera=None):
        self.camera = camera or FakeCamera()
        self.engine = engine or ScriptedEngine()
        self.led = RecordingLed()
        self.sent = []
        self.now = 0.0
        self.commands = queue.Queue()
        self.loop = GameLoop(self.camera, self.engine, self.led, self.sent.append, clock=lambda: self.now)
        self.loop.start()

    def step(self, *commands):
        for cmd in commands:
            self.commands.put(cmd)
        self.loop.step(self.commands)
        return self.state

    @property
    def state(self):
        return self.of_type("state")[-1]

    def of_type(self, kind):
        return [msg for msg in self.sent if msg["type"] == kind]

    def play(self, uci):
        """Make a move on the (fake) board from the current position."""
        board = chess.Board(self.state["fen"])
        board.push_uci(uci)
        self.camera.occupancy = occupancy_from_fen(board.fen())

    def start_game(self, color="white", mode="play"):
        return self.step({"type": "start_game", "human_color": color, "elo": 1500, "mode": mode})


def test_start_sends_info_then_idle():
    game = Game()
    assert game.sent[0] == {"type": "info", "version": "1", "elo_min": 1320, "elo_max": 3190,
                            "engine_name": "FakeGameEngine"}
    state = game.state
    assert state["phase"] == "idle"
    assert state["fen"] is None and state["mode"] is None and state["moves_san"] == []
    assert state["devices"] == {"camera": "ok", "engine": "ok", "led": "ok"}
    assert game.led.lit == {}


def test_state_is_only_sent_when_it_changes():
    game = Game()
    count = len(game.sent)
    game.step()
    game.step()
    assert len(game.sent) == count


def test_setup_check_marks_wrong_squares_until_the_board_is_right():
    game = Game()
    game.camera.occupancy = START_OCC.replace("W", ".", 1)  # a1 rook missing
    state = game.start_game()
    assert state["phase"] == "setup_check"
    assert state["board_problem"]["squares"] == ["a1"]
    assert game.led.lit == {"a1": "error"}

    game.camera.occupancy = START_OCC
    state = game.step()
    assert state["phase"] == "human_turn"
    assert state["board_problem"] is None
    assert game.led.lit == {}


def test_unstable_observations_are_ignored():
    game = Game()
    game.camera.stable = False
    assert game.start_game()["phase"] == "setup_check"
    game.camera.stable = True
    assert game.step()["phase"] == "human_turn"


def test_human_move_engine_move_and_its_confirmation():
    game = Game(ScriptedEngine(["e7e5"]))
    game.start_game()
    game.play("e2e4")
    state = game.step()
    assert state["phase"] == "engine_thinking"
    assert state["moves_san"] == ["e4"]
    assert state["rating"]["played"] == "e2e4"
    assert state["evaluation"] == {"fen": state["fen"], "score_cp": 0, "mate_in": None}

    state = game.step()
    assert state["phase"] == "engine_move_pending"
    assert state["engine_move"]["move"] == "e7e5"
    assert state["message"] == "Play the computer's move: e5 (e7→e5)"
    assert game.led.lit == {"e7": "engine_from", "e5": "engine_to"}

    game.play("e7e5")
    state = game.step()
    assert state["phase"] == "human_turn"
    assert state["moves_san"] == ["e4", "e5"]
    assert state["engine_move"] is None
    assert state["rating"]["played"] == "e7e5" == state["last_move"]
    assert game.led.lit == {}


def test_old_analysis_is_cleared_before_the_new_position_is_rated():
    game = Game()
    game.start_game()
    game.play("e2e4")
    game.step()
    after_move = [s for s in game.of_type("state") if s["last_move"] == "e2e4"]
    assert after_move[0]["rating"] is None and after_move[0]["evaluation"] is None
    assert after_move[-1]["rating"] is not None


def test_illegal_move_shows_a_problem_until_put_back():
    game = Game()
    game.start_game()
    occ = list(START_OCC)
    occ[12], occ[36] = ".", "W"  # e2 pawn put on e5
    game.camera.occupancy = "".join(occ)
    state = game.step()
    assert state["phase"] == "human_turn"
    assert state["board_problem"]["squares"] == ["e2", "e5"]
    assert state["message"] == state["board_problem"]["text"]
    assert game.led.lit == {"e2": "error", "e5": "error"}

    game.camera.occupancy = START_OCC
    state = game.step()
    assert state["board_problem"] is None
    assert state["message"] == "Your move."
    assert game.led.lit == {}


def test_wrong_engine_move_marks_the_squares_that_differ_from_its_result():
    game = Game(ScriptedEngine(["e7e5"]))
    game.start_game()
    game.play("e2e4")
    game.step()
    game.step()
    game.play("e7e6")  # instead of e7e5
    state = game.step()
    assert state["phase"] == "engine_move_pending"
    assert state["board_problem"]["squares"] == ["e5", "e6"]
    # The computer's move stays lit; e5 is both, and the error wins.
    assert game.led.lit == {"e5": "error", "e6": "error", "e7": "engine_from"}

    game.play("e7e5")
    assert game.step()["phase"] == "human_turn"


def test_hint_is_shown_until_the_next_move():
    game = Game()
    game.start_game()
    state = game.step({"type": "hint"})
    assert state["hint"]["move"] == state["hint"]["from"] + state["hint"]["to"]
    assert "Hint:" in state["message"]
    assert set(game.led.lit.values()) == {"hint_from", "hint_to"}

    game.play("e2e4")
    state = game.step()
    assert state["hint"] is None


def test_promotion_asks_for_the_piece():
    # 1. e4 d5 2. exd5 c6 3. dxc6 Nf6 4. cxb7 e6 5. bxa8=?
    game = Game(ScriptedEngine(["d7d5", "c7c6", "g8f6", "e7e6"]))
    game.start_game()
    for human, computer in (("e2e4", "d7d5"), ("e4d5", "c7c6"), ("d5c6", "g8f6"), ("c6b7", "e7e6")):
        game.play(human)
        game.step()
        game.step()
        game.play(computer)
        assert game.step()["phase"] == "human_turn"

    game.play("b7a8q")  # the camera can't see which piece
    state = game.step()
    assert state["phase"] == "promotion_choice"
    assert state["promotion"] == {"from": "b7", "to": "a8", "choices": ["q", "r", "b", "n"]}

    state = game.step({"type": "promote", "piece": "n"})
    assert state["last_move"] == "b7a8n"
    assert state["moves_san"][-1] == "bxa8=N"


def test_putting_the_pawn_back_leaves_promotion_choice():
    game = Game(ScriptedEngine(["d7d5", "c7c6", "g8f6", "e7e6"]))
    game.start_game()
    for human, computer in (("e2e4", "d7d5"), ("e4d5", "c7c6"), ("d5c6", "g8f6"), ("c6b7", "e7e6")):
        game.play(human)
        game.step()
        game.step()
        game.play(computer)
        game.step()
    before = game.camera.occupancy
    game.play("b7a8q")
    assert game.step()["phase"] == "promotion_choice"
    game.camera.occupancy = before
    state = game.step()
    assert state["phase"] == "human_turn"
    assert state["promotion"] is None


def test_checkmate_as_black():
    game = Game(ScriptedEngine(["f2f3", "g2g4"]))
    state = game.start_game("black")
    assert state["phase"] == "engine_thinking"  # black: the computer starts
    for computer, human in (("f2f3", "e7e5"), ("g2g4", "d8h4")):
        assert game.step()["phase"] == "engine_move_pending"
        game.play(computer)
        assert game.step()["phase"] == "human_turn"
        game.play(human)
        state = game.step()
    assert state["phase"] == "game_over"
    assert state["result"] == "0-1"
    assert state["termination"] == "CHECKMATE"
    assert state["message"] == "Checkmate. You win!"
    assert game.led.lit == {}


def test_resign_and_cancel():
    game = Game()
    game.start_game()
    state = game.step({"type": "resign"})
    assert state["phase"] == "game_over"
    assert state["result"] == "0-1" and state["termination"] == "RESIGNATION"
    assert state["message"] == "You resigned. The computer wins."

    state = game.step({"type": "cancel"})
    assert state["phase"] == "idle"
    assert state["fen"] is None and state["result"] is None


def test_random_color():
    game = Game()
    assert game.start_game("random")["human_color"] in ("white", "black")


def test_command_not_allowed_in_this_phase_is_a_toast():
    game = Game()
    count = len(game.of_type("state"))
    game.step({"type": "hint"})
    assert game.of_type("toast")[-1]["level"] == "error"
    assert len(game.of_type("state")) == count  # a rejected command doesn't change state


def test_camera_failure_after_the_grace_time_and_retry():
    game = Game()
    game.start_game()
    game.camera.started = False  # get_observation() -> CAMERA_NOT_READY
    assert game.step()["phase"] == "human_turn"
    game.now += CAMERA_GRACE_S
    state = game.step()
    assert state["phase"] == "error"
    assert state["devices"]["camera"] == "error"
    assert state["message"].startswith("Camera problem: camera not started")

    state = game.step({"type": "retry"})  # FakeCamera.start() works again
    assert state["phase"] == "human_turn"
    assert state["devices"]["camera"] == "ok"


def test_engine_failure_and_retry_restarts_it_and_asks_again():
    engine = ScriptedEngine()
    game = Game(engine)
    game.start_game()
    good = engine.get_engine_move
    engine.get_engine_move = lambda: err("ENGINE_ERROR", "Stockfish died")
    game.play("e2e4")
    game.step()
    state = game.step()
    assert state["phase"] == "error"
    assert state["devices"]["engine"] == "error"
    assert state["moves_san"] == ["e4"]  # the game is kept

    engine.get_engine_move = good
    state = game.step({"type": "retry"})
    assert engine.starts == 2
    assert game.of_type("info")[-1]["engine_name"] == "FakeGameEngine"
    assert state["phase"] == "engine_move_pending"


def test_engine_that_fails_to_start():
    engine = ScriptedEngine()
    engine.start = lambda: err("ENGINE_ERROR", "no Stockfish at /usr/games/stockfish")
    game = Game(engine)
    assert game.of_type("info")[0]["engine_name"] is None
    assert game.state["phase"] == "error"
    assert "Press Retry" in game.state["message"]


def test_failed_analysis_is_a_warning_and_the_game_goes_on():
    engine = ScriptedEngine()
    engine.rate_last_move = lambda: err("ENGINE_ERROR", "analysis timed out")
    game = Game(engine)
    game.start_game()
    game.play("e2e4")
    state = game.step()
    assert state["phase"] == "engine_thinking"
    assert state["rating"] is None and state["evaluation"] is None
    assert game.of_type("toast")[-1]["level"] == "warning"


def test_unplugged_leds_are_not_an_error_phase():
    game = Game(ScriptedEngine(["e7e5"]))
    game.start_game()
    game.led.connected = False
    game.play("e2e4")
    game.step()
    state = game.step()
    assert state["phase"] == "engine_move_pending"
    assert state["devices"]["led"] == "error"


def test_uncalibrated_camera_then_calibrate():
    camera = FakeCamera()
    camera.start = lambda: {"ok": True, "calibrated": False}
    game = Game(camera=camera)
    assert game.state["phase"] == "idle"
    assert game.state["devices"]["camera"] == "error"
    assert "Calibrate" in game.state["message"]

    state = game.step({"type": "calibrate"})
    assert [s["phase"] for s in game.of_type("state")][-2:] == ["calibrating", "idle"]
    assert state["devices"]["camera"] == "ok"
    assert game.of_type("toast")[-1] == {"type": "toast", "level": "info", "text": "Camera calibrated"}


def test_debug_image_request_is_answered_in_the_loop():
    game = Game()
    request = DebugImageRequest()
    game.step(request)
    assert request.reply.result(timeout=0) is None  # FakeCamera has no image


@pytest.mark.parametrize("move, lit", [
    ({"from": "e7", "to": "e5", "rook_from": None, "rook_to": None, "capture_square": None},
     {"e7": "engine_from", "e5": "engine_to"}),
    ({"from": "e4", "to": "d5", "rook_from": None, "rook_to": None, "capture_square": "d5"},
     {"e4": "engine_from", "d5": "engine_to"}),
    ({"from": "e8", "to": "g8", "rook_from": "h8", "rook_to": "f8", "capture_square": None},
     {"e8": "engine_from", "h8": "engine_from", "g8": "engine_to", "f8": "engine_to"}),
    ({"from": "d4", "to": "e3", "rook_from": None, "rook_to": None, "capture_square": "e4"},
     {"d4": "engine_from", "e4": "engine_from", "e3": "engine_to"}),
])
def test_engine_move_squares_follow_table_4_2(move, lit):
    assert {item["sq"]: item["role"] for item in engine_move_squares(move)} == lit


def test_describe_engine_move():
    castle = {"san": "O-O", "from": "e1", "to": "g1", "rook_from": "h1", "rook_to": "f1",
              "capture_square": None, "promotion": None}
    assert describe_engine_move(castle) == "Play the computer's move: O-O (e1→g1, rook h1→f1)"
    en_passant = {"san": "dxe3", "from": "d4", "to": "e3", "rook_from": None, "rook_to": None,
                  "capture_square": "e4", "promotion": None}
    assert describe_engine_move(en_passant) == \
        "Play the computer's move: dxe3 (d4→e3, remove the pawn on e4)"
    promotion = {"san": "a1=Q", "from": "a2", "to": "a1", "rook_from": None, "rook_to": None,
                 "capture_square": None, "promotion": "q"}
    assert describe_engine_move(promotion) == "Play the computer's move: a1=Q (a2→a1, put a queen on a1)"
