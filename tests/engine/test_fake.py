"""FakeGameEngine (contracts/interfaces.md section 3.9) and the shared board logic in
base.py. No Stockfish binary required."""

import subprocess
import sys
from pathlib import Path

import chess
import pytest

from checkmate.engine import FakeGameEngine

REPO_ROOT = Path(__file__).resolve().parents[2]

START_FEN = chess.STARTING_FEN


@pytest.fixture
def engine():
    eng = FakeGameEngine({})
    eng.start()
    eng.new_game("white", 1500, "play")
    return eng


# -- lifecycle & new_game --------------------------------------------------------------------

def test_start_reports_name_and_elo_range():
    eng = FakeGameEngine({})
    res = eng.start()
    assert res["ok"] is True
    assert res["engine_name"] == "FakeGameEngine"
    assert res["elo_min"] <= 1500 <= res["elo_max"]


def test_new_game_before_start_is_not_started():
    eng = FakeGameEngine({})
    assert eng.new_game("white", 1500)["error"] == "NOT_STARTED"


def test_new_game_returns_start_position():
    eng = FakeGameEngine({})
    eng.start()
    state = eng.new_game("black", 1800, "practice")
    assert state["ok"] is True
    assert state["fen"] == START_FEN
    assert state["turn"] == "white"
    assert state["human_color"] == "black"
    assert state["mode"] == "practice"
    assert state["moves_uci"] == [] and state["moves_san"] == []
    assert state["last_move"] is None
    assert state["game_over"] is False


@pytest.mark.parametrize("elo,expected", [(50, 1320), (99999, 3190), (1700, 1700)])
def test_new_game_clamps_elo(elo, expected):
    eng = FakeGameEngine({})
    eng.start()
    assert eng.new_game("white", elo)["elo"] == expected


@pytest.mark.parametrize("args", [
    ("sideways", 1500, "play"),     # bad color
    ("white", 1500, "blitz"),       # bad mode
    ("white", "strong", "play"),    # bad elo type
    ("white", True, "play"),        # bool is not an int
    (["white"], 1500, "play"),      # not a string
    ("white", 1500, {"play": 1}),   # not a string
])
def test_new_game_bad_request(args):
    eng = FakeGameEngine({})
    eng.start()
    assert eng.new_game(*args)["error"] == "BAD_REQUEST"


# -- guards before a game exists -------------------------------------------------------------

def test_calls_before_new_game_return_no_game():
    eng = FakeGameEngine({})
    eng.start()
    for res in (eng.state(), eng.push_move("e2e4"), eng.get_engine_move(),
                eng.get_hint(), eng.rate_last_move(), eng.resign("white")):
        assert res["error"] == "NO_GAME"


# -- push_move -------------------------------------------------------------------------------

def test_push_move_legal_updates_state(engine):
    res = engine.push_move("e2e4")
    assert res["ok"] is True and res["san"] == "e4"
    state = res["state"]
    assert state["turn"] == "black"
    assert state["moves_uci"] == ["e2e4"] and state["moves_san"] == ["e4"]
    assert state["last_move"] == "e2e4"
    assert state["fullmove_number"] == 1


def test_push_move_illegal(engine):
    assert engine.push_move("e2e5")["error"] == "ILLEGAL_MOVE"


@pytest.mark.parametrize("bad", ["not-a-move", "e2", "z9z9", 1234])
def test_push_move_bad_request(engine, bad):
    assert engine.push_move(bad)["error"] == "BAD_REQUEST"


def test_in_check_and_check_square():
    eng = FakeGameEngine({})
    eng.start()
    eng.new_game("white", 1500)
    # Scholar's-mate-ish check: 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6 4.Qxf7+
    for mv in ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"]:
        eng.push_move(mv)
    state = eng.state()
    assert state["in_check"] is True
    assert state["check_square"] == "e8"  # black king
    assert state["turn"] == "black"


# -- get_engine_move / get_hint (first legal move for the fake) ------------------------------

def test_engine_move_is_legal_and_does_not_change_board(engine):
    before = engine.state()["fen"]
    res = engine.get_engine_move()
    assert res["ok"] is True
    assert chess.Move.from_uci(res["move"]) in chess.Board(before).legal_moves
    assert engine.state()["fen"] == before  # get_engine_move must not apply the move


def test_hint_is_legal(engine):
    assert engine.get_hint()["ok"] is True


# -- rate_last_move --------------------------------------------------------------------------

def test_rate_last_move_needs_a_move(engine):
    assert engine.rate_last_move()["error"] == "BAD_REQUEST"


def test_rate_last_move_is_good(engine):
    engine.push_move("e2e4")
    res = engine.rate_last_move()
    assert res["ok"] is True
    assert res["rating"] == "good"
    assert res["played"] == "e2e4"
    assert res["cp_loss"] == 0


# -- resign & game over ----------------------------------------------------------------------

def test_resign_ends_game(engine):
    engine.push_move("e2e4")
    state = engine.resign("white")
    assert state["game_over"] is True
    assert state["result"] == "0-1"
    assert state["termination"] == "RESIGNATION"
    # No more moves once the game is over.
    assert engine.push_move("e7e5")["error"] == "GAME_OVER"


@pytest.mark.parametrize("bad", ["grey", {}, None])
def test_resign_bad_color(engine, bad):
    assert engine.resign(bad)["error"] == "BAD_REQUEST"


def test_resign_after_checkmate_keeps_the_result(engine):
    for mv in ["f2f3", "e7e5", "g2g4", "d8h4"]:  # fool's mate: black wins
        engine.push_move(mv)
    assert engine.resign("black")["error"] == "GAME_OVER"
    state = engine.state()
    assert state["result"] == "0-1" and state["termination"] == "CHECKMATE"


def test_engine_package_does_not_need_opencv():
    # The engine must import on a machine without the camera's dependencies (section 0.2).
    code = "import sys, checkmate.engine; assert 'cv2' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True, cwd=REPO_ROOT)


# -- move-detail dict for every move type (white-box: craft the position directly) -----------
# The public API only ever starts from START_FEN, so to exercise the LED/UI detail fields
# (section 3.5) for special moves we set the private board to a crafted FEN and call the
# shared helper directly.

def _details(fen, uci):
    eng = FakeGameEngine({})
    eng.start()
    eng.new_game("white", 1500)
    eng._board = chess.Board(fen)
    return eng._move_details(chess.Move.from_uci(uci))


def test_details_normal_move():
    d = _details(START_FEN, "e2e4")
    assert (d["from"], d["to"]) == ("e2", "e4")
    assert d["san"] == "e4"
    assert d["rook_from"] is None and d["capture_square"] is None and d["promotion"] is None


def test_details_capture():
    fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    d = _details(fen, "e4d5")
    assert d["capture_square"] == "d5" and d["san"] == "exd5"


def test_details_kingside_castling():
    fen = "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    d = _details(fen, "e1g1")
    assert d["san"] == "O-O"
    assert (d["from"], d["to"]) == ("e1", "g1")
    assert (d["rook_from"], d["rook_to"]) == ("h1", "f1")


def test_details_queenside_castling():
    fen = "r3kbnr/pppqpppp/2n5/3p4/3P1b2/2N1B3/PPPQPPPP/R3KBNR w KQkq - 6 5"
    d = _details(fen, "e1c1")
    assert d["san"] == "O-O-O"
    assert (d["rook_from"], d["rook_to"]) == ("a1", "d1")


def test_details_en_passant():
    fen = "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"
    d = _details(fen, "e5d6")
    assert (d["from"], d["to"]) == ("e5", "d6")
    assert d["capture_square"] == "d5"  # the captured pawn's real square


def test_details_promotion():
    fen = "8/4P1k1/8/8/8/8/6K1/8 w - - 0 1"
    d = _details(fen, "e7e8q")
    assert d["promotion"] == "q" and (d["from"], d["to"]) == ("e7", "e8")
