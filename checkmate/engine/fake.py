"""FakeGameEngine (contracts/interfaces.md section 3.9): same interface as GameEngine, but
python-chess only, no Stockfish. For teammates building against the engine without a binary.

get_engine_move()/get_hint() return the first legal move; rate_last_move() always rates the
move "good". Board state, state(), push_move() and resign() behave exactly like the real
engine (shared in base.py).
"""

import chess

from checkmate.engine.base import ELO_MAX, ELO_MIN, BaseChessGame
from checkmate.errors import err


class FakeGameEngine(BaseChessGame):
    def start(self) -> dict:
        self._started = True
        self._engine_name = "FakeGameEngine"
        self._elo_min = ELO_MIN
        self._elo_max = ELO_MAX
        return self._start_info()

    def close(self) -> None:
        self._started = False

    def _first_legal(self) -> dict:
        guard = self._require_started() or self._require_game()
        if guard:
            return guard
        if self._game_over():
            return err("GAME_OVER", "the game has ended; no move to make")
        move = next(iter(self._board.legal_moves), None)
        if move is None:
            return err("GAME_OVER", "no legal moves")
        return self._move_details(move)

    def get_engine_move(self) -> dict:
        return self._first_legal()

    def get_hint(self) -> dict:
        return self._first_legal()

    def rate_last_move(self) -> dict:
        guard = self._require_started() or self._require_game()
        if guard:
            return guard
        if not self._board.move_stack:
            return err("BAD_REQUEST", "no moves have been played yet")
        played = self._board.peek()
        return {
            "ok": True,
            "played": played.uci(),
            "played_san": self._moves_san[-1],
            "best": played.uci(),
            "best_san": self._moves_san[-1],
            "score_before": 0,
            "score_after": 0,
            "mate_in": None,
            "cp_loss": 0,
            "rating": "good",
        }
