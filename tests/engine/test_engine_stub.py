"""GameEngine's own logic (strength settings, restart after a crash) with a stand-in for
Stockfish, so these run without the binary. test_engine.py covers the real Stockfish."""

from types import SimpleNamespace

import chess
import chess.engine
import pytest

from checkmate.engine import GameEngine


class StubStockfish:
    """Just enough of chess.engine.SimpleEngine for GameEngine."""

    def __init__(self):
        self.id = {"name": "Stockfish stub"}
        self.options = {"UCI_Elo": SimpleNamespace(min=1320, max=3190)}
        self.configured = []
        self.alive = True

    def configure(self, options):
        self.configured.append(dict(options))

    def ping(self):
        if not self.alive:
            raise chess.engine.EngineTerminatedError("engine process died")

    def play(self, board, limit):
        self.ping()
        return chess.engine.PlayResult(next(iter(board.legal_moves)), None)

    def quit(self):
        self.alive = False


@pytest.fixture
def stubs(monkeypatch):
    """Every Stockfish the engine starts, oldest first."""
    started = []

    def popen_uci(path):
        started.append(StubStockfish())
        return started[-1]

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", popen_uci)
    return started


@pytest.fixture
def engine(stubs):
    eng = GameEngine({"stockfish_path": "stockfish", "think_time_s": 0.1})
    assert eng.start()["ok"] is True
    yield eng
    eng.close()


def elos(stub):
    return [c["UCI_Elo"] for c in stub.configured if "UCI_Elo" in c]


def test_each_new_game_sets_its_own_elo(engine, stubs):
    engine.new_game("white", 1500)
    engine.new_game("white", 2200)
    assert elos(stubs[0]) == [1500, 2200]


def test_engine_move_after_a_hint_plays_at_the_game_elo(engine, stubs):
    engine.new_game("white", 1500)
    assert engine.get_hint()["ok"] is True  # full strength
    assert engine.get_engine_move()["ok"] is True
    assert stubs[0].configured[-1] == {"UCI_LimitStrength": True, "UCI_Elo": 1500}


def test_start_again_keeps_a_live_engine(engine, stubs):
    assert engine.start()["ok"] is True
    assert len(stubs) == 1


def test_start_again_replaces_a_crashed_engine(engine, stubs):
    engine.new_game("white", 1500)
    engine.push_move("e2e4")
    stubs[0].alive = False
    assert engine.get_engine_move()["error"] == "ENGINE_ERROR"

    assert engine.start()["ok"] is True
    assert len(stubs) == 2
    assert engine.get_engine_move()["ok"] is True
    assert elos(stubs[1]) == [1500]               # the game's strength is set again
    assert engine.state()["moves_uci"] == ["e2e4"]  # the game goes on
