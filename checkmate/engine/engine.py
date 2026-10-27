"""GameEngine: python-chess board + a local Stockfish (contracts/interfaces.md section 3).

Wraps one chess.Board (shared logic in base.py) and a Stockfish process started with
chess.engine.SimpleEngine.popen_uci(config["stockfish_path"]). get_engine_move() plays at
the limited Elo chosen for the game; get_hint() and rate_last_move() use full strength
(sections 3.6, 3.7), so UCI_LimitStrength is toggled around those calls.
"""

import chess
import chess.engine

from checkmate.engine.base import BaseChessGame
from checkmate.errors import err

# Large finite value standing in for a forced mate when turning scores into centipawns, so
# cp_loss is always a real number even when one side is mating.
MATE_CP = 100_000

# cp_loss thresholds for rate_last_move() (section 3.7). Joel may tune these.
RATING_THRESHOLDS = (("best", 10), ("good", 50), ("inaccuracy", 100), ("mistake", 300))


def _rating_for(cp_loss: int) -> str:
    for name, limit in RATING_THRESHOLDS:
        if cp_loss <= limit:
            return name
    return "blunder"


class GameEngine(BaseChessGame):
    def __init__(self, config: dict):
        super().__init__(config)
        self._engine = None
        self._think_time = float(self._config.get("think_time_s", 1.0))
        self._limited_now = None  # cache so we only reconfigure strength when it changes

    # -- lifecycle (section 3.1) -----------------------------------------------------------

    def start(self) -> dict:
        if self._engine is not None:
            return {
                "ok": True,
                "engine_name": self._engine_name,
                "elo_min": self._elo_min,
                "elo_max": self._elo_max,
            }
        path = self._config.get("stockfish_path")
        try:
            engine = chess.engine.SimpleEngine.popen_uci(path)
            engine.configure({
                "Threads": int(self._config.get("threads", 2)),
                "Hash": int(self._config.get("hash_mb", 64)),
            })
        except Exception as e:
            return err("ENGINE_ERROR", f"could not start Stockfish at {path!r}: {e}")

        self._engine = engine
        self._engine_name = engine.id.get("name", "Stockfish")
        elo_opt = engine.options.get("UCI_Elo")
        self._elo_min = int(elo_opt.min) if elo_opt and elo_opt.min is not None else 1320
        self._elo_max = int(elo_opt.max) if elo_opt and elo_opt.max is not None else 3190
        self._started = True
        self._limited_now = None
        return {
            "ok": True,
            "engine_name": self._engine_name,
            "elo_min": self._elo_min,
            "elo_max": self._elo_max,
        }

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
        self._started = False

    def _on_new_game(self) -> None:
        # Play at the chosen Elo until a full-strength call (hint/rating) toggles it.
        self._apply_strength(limited=True)

    # -- strength toggle -------------------------------------------------------------------

    def _apply_strength(self, limited: bool) -> None:
        if self._limited_now == limited:
            return
        if limited:
            self._engine.configure({"UCI_LimitStrength": True, "UCI_Elo": self._elo})
        else:
            self._engine.configure({"UCI_LimitStrength": False})
        self._limited_now = limited

    # -- engine move / hint (sections 3.5, 3.6) --------------------------------------------

    def _best_move(self, limited: bool) -> dict:
        guard = self._require_started() or self._require_game()
        if guard:
            return guard
        if self._game_over():
            return err("GAME_OVER", "the game has ended; no move to make")
        try:
            self._apply_strength(limited)
            result = self._engine.play(self._board, chess.engine.Limit(time=self._think_time))
        except Exception as e:
            return err("ENGINE_ERROR", f"Stockfish failed: {e}")
        if result.move is None:
            return err("ENGINE_ERROR", "Stockfish returned no move")
        return self._move_details(result.move)

    def get_engine_move(self) -> dict:
        return self._best_move(limited=True)

    def get_hint(self) -> dict:
        return self._best_move(limited=False)

    # -- rate_last_move (section 3.7) ------------------------------------------------------

    def rate_last_move(self) -> dict:
        guard = self._require_started() or self._require_game()
        if guard:
            return guard
        if not self._board.move_stack:
            return err("BAD_REQUEST", "no moves have been played yet")

        board_after = self._board
        board_before = board_after.copy()
        played = board_before.pop()
        played_san = self._moves_san[-1]
        mover_is_white = board_before.turn == chess.WHITE

        try:
            self._apply_strength(limited=False)
            limit = chess.engine.Limit(time=self._think_time)
            info_before = self._engine.analyse(board_before, limit)
            best_move = info_before["pv"][0]
            best_san = board_before.san(best_move)
            score_before = info_before["score"].white()
            score_after_field, mate_in, sa_cp = self._eval_after(board_after, limit)
        except Exception as e:
            return err("ENGINE_ERROR", f"Stockfish analysis failed: {e}")

        sb_cp = score_before.score(mate_score=MATE_CP)
        sign = 1 if mover_is_white else -1
        cp_loss = max(0, sign * (sb_cp - sa_cp))

        return {
            "ok": True,
            "played": played.uci(),
            "played_san": played_san,
            "best": best_move.uci(),
            "best_san": best_san,
            "score_before": None if score_before.is_mate() else score_before.score(),
            "score_after": score_after_field,
            "mate_in": mate_in,
            "cp_loss": cp_loss,
            "rating": _rating_for(cp_loss),
        }

    def _eval_after(self, board_after, limit):
        """White-POV evaluation of the position after the played move.

        Returns (score_after_field, mate_in, sa_cp): the centipawn score for the `state`
        field (None on a mate), the signed mate distance (positive = White mates, None if
        no mate), and a finite centipawn value for the cp_loss math. Terminal positions are
        handled here because Stockfish will not analyse them.
        """
        if board_after.is_checkmate():
            # Side to move is mated, so the mover just won. A terminal mate has distance 0;
            # the winner is read from result/termination (section 5.3.1), but the cp value
            # still needs the right sign so cp_loss stays ~0 for the mating move.
            winner_white = board_after.turn == chess.BLACK
            return None, 0, (MATE_CP if winner_white else -MATE_CP)
        if board_after.is_game_over(claim_draw=True):
            return 0, None, 0
        score = self._engine.analyse(board_after, limit)["score"].white()
        field = None if score.is_mate() else score.score()
        return field, score.mate(), score.score(mate_score=MATE_CP)
