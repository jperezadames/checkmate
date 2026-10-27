"""GameEngine with a real Stockfish (contracts/interfaces.md section 3).

Skipped automatically when no Stockfish binary is found. On the Pi the binary is at
config.json's stockfish_path (/usr/games/stockfish); on a laptop it is usually on PATH
(e.g. `brew install stockfish`), so we try the config path first, then PATH.
"""

import json
import shutil
from pathlib import Path

import chess
import pytest

from checkmate.engine import GameEngine

REPO_ROOT = Path(__file__).resolve().parents[2]


def _stockfish_path():
    configured = json.loads((REPO_ROOT / "config.json").read_text())["engine"]["stockfish_path"]
    if Path(configured).exists():
        return configured
    return shutil.which("stockfish")


STOCKFISH = _stockfish_path()
pytestmark = pytest.mark.skipif(STOCKFISH is None, reason="no Stockfish binary found")


@pytest.fixture(scope="module")
def started():
    """One Stockfish process shared by the module (starting it is the slow part)."""
    eng = GameEngine({"stockfish_path": STOCKFISH, "threads": 1, "hash_mb": 16,
                      "think_time_s": 0.1})
    info = eng.start()
    assert info["ok"] is True
    yield eng, info
    eng.close()


@pytest.fixture
def engine(started):
    eng, _ = started
    eng.new_game("white", 1500, "play")
    return eng


def test_start_reports_stockfish_and_elo_range(started):
    _, info = started
    assert "Stockfish" in info["engine_name"]
    assert isinstance(info["elo_min"], int) and isinstance(info["elo_max"], int)
    assert info["elo_min"] <= info["elo_max"]


def test_start_missing_binary_is_engine_error():
    eng = GameEngine({"stockfish_path": "/nonexistent/stockfish"})
    assert eng.start()["error"] == "ENGINE_ERROR"


def test_new_game_clamps_elo_to_engine_range(started):
    eng, info = started
    assert eng.new_game("white", 1)["elo"] == info["elo_min"]
    assert eng.new_game("white", 10_000)["elo"] == info["elo_max"]


def test_engine_move_is_legal_and_leaves_board_unchanged(engine):
    before = engine.state()["fen"]
    res = engine.get_engine_move()
    assert res["ok"] is True
    assert chess.Move.from_uci(res["move"]) in chess.Board(before).legal_moves
    assert engine.state()["fen"] == before  # section 3.5: does not apply the move


def test_play_a_few_moves(engine):
    # Human move, then let the engine reply and confirm it.
    assert engine.push_move("e2e4")["ok"] is True
    m = engine.get_engine_move()
    assert m["ok"] is True
    pushed = engine.push_move(m["move"])
    assert pushed["ok"] is True
    state = pushed["state"]
    assert state["moves_uci"][0] == "e2e4"
    assert len(state["moves_uci"]) == 2 and len(state["moves_san"]) == 2


def test_hint_is_a_legal_move(engine):
    hint = engine.get_hint()
    assert hint["ok"] is True
    assert chess.Move.from_uci(hint["move"]) in chess.Board(engine.state()["fen"]).legal_moves


def test_rate_last_move_structure(engine):
    engine.push_move("e2e4")
    res = engine.rate_last_move()
    assert res["ok"] is True
    assert res["played"] == "e2e4"
    assert res["rating"] in {"best", "good", "inaccuracy", "mistake", "blunder"}
    assert res["cp_loss"] >= 0


def test_rate_last_move_needs_a_move(engine):
    assert engine.rate_last_move()["error"] == "BAD_REQUEST"


def test_fools_mate_is_detected_and_rated(started):
    """1.f3 e5 2.g4 Qh4# — the fastest checkmate. Exercises terminal state + rating."""
    eng, _ = started
    eng.new_game("white", 1500)
    for mv in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        assert eng.push_move(mv)["ok"] is True
    state = eng.state()
    assert state["game_over"] is True
    assert state["result"] == "0-1"
    assert state["termination"] == "CHECKMATE"
    # The mating move should rate as the best available, with a terminal (zero-distance) mate.
    rating = eng.rate_last_move()
    assert rating["ok"] is True
    assert rating["rating"] == "best"
    assert rating["mate_in"] == 0
    assert rating["score_after"] is None
    # No further moves once mated.
    assert eng.push_move("e1e2")["error"] == "GAME_OVER"


def test_get_engine_move_after_game_over(started):
    eng, _ = started
    eng.new_game("white", 1500)
    for mv in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        eng.push_move(mv)
    assert eng.get_engine_move()["error"] == "GAME_OVER"


def test_resign(engine):
    state = engine.resign("white")
    assert state["result"] == "0-1"
    assert state["termination"] == "RESIGNATION"
    assert state["game_over"] is True
