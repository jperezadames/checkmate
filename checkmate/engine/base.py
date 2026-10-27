"""Shared chess-board state for the engine package (contracts/interfaces.md section 3).

`GameEngine` (real Stockfish) and `FakeGameEngine` (no Stockfish) hold the same
`chess.Board` and report it the same way. Everything that does not need Stockfish lives
here: new_game bookkeeping, state(), push_move(), resign(), and the move-detail dict used
by get_engine_move()/get_hint(). The two subclasses add only the engine-specific calls.

No method here raises to main; they return err(CODE, message) (section 1.5). The board is
the only game state in the system (section 0.2, 0.4), so nothing returned is a chess.Board.
"""

import chess

from checkmate.camera.occupancy import START_FEN
from checkmate.errors import err

COLORS = {"white": chess.WHITE, "black": chess.BLACK}
MODES = ("play", "practice")


def _square(name_square: int) -> str:
    return chess.square_name(name_square)


class BaseChessGame:
    """Board + move history shared by the real and fake engines."""

    def __init__(self, config: dict):
        self._config = config or {}
        self._board = None            # chess.Board once new_game is called, else None
        self._human_color = None      # "white" / "black"
        self._elo = None
        self._mode = None
        self._moves_san = []          # SAN of each played move, same length as move_stack
        self._resignation = None      # ("1-0" | "0-1", ) winner result when a side resigned
        self._started = False
        # Filled in by the subclass's start(); the UI difficulty slider reads these.
        self._elo_min = None
        self._elo_max = None
        self._engine_name = None

    # -- lifecycle hooks the subclasses override -------------------------------------------

    def start(self) -> dict:  # pragma: no cover - overridden
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def _on_new_game(self) -> None:
        """Called by new_game() after the board is reset. Subclasses configure the engine
        here (e.g. set UCI_Elo). May raise; new_game() turns that into ENGINE_ERROR."""

    # -- guards ---------------------------------------------------------------------------

    def _require_game(self):
        if self._board is None:
            return err("NO_GAME", "new_game has not been called")
        return None

    def _require_started(self):
        if not self._started:
            return err("NOT_STARTED", "start() was not called or failed")
        return None

    # -- new_game (section 3.2) ------------------------------------------------------------

    def new_game(self, human_color: str, elo: int, mode: str = "play") -> dict:
        not_started = self._require_started()
        if not_started:
            return not_started
        if human_color not in COLORS:
            return err("BAD_REQUEST", 'human_color must be "white" or "black"')
        if mode not in MODES:
            return err("BAD_REQUEST", 'mode must be "play" or "practice"')
        if isinstance(elo, bool) or not isinstance(elo, int):
            return err("BAD_REQUEST", "elo must be an int")

        clamped = max(self._elo_min, min(self._elo_max, elo))
        self._board = chess.Board(START_FEN)
        self._moves_san = []
        self._resignation = None
        self._human_color = human_color
        self._elo = clamped
        self._mode = mode
        try:
            self._on_new_game()
        except Exception as e:  # engine configure failed; keep contract (never raise to main)
            self._board = None
            return err("ENGINE_ERROR", f"could not configure engine for new game: {e}")
        return self.state()

    # -- state (section 3.3) ---------------------------------------------------------------

    def _outcome(self):
        """Return (result, termination) or (None, None). Resignation wins over the board."""
        if self._resignation is not None:
            return self._resignation, "RESIGNATION"
        outcome = self._board.outcome(claim_draw=True)
        if outcome is None:
            return None, None
        return outcome.result(), outcome.termination.name

    def _game_over(self) -> bool:
        return self._resignation is not None or self._board.is_game_over(claim_draw=True)

    def state(self) -> dict:
        no_game = self._require_game()
        if no_game:
            return no_game
        board = self._board
        result, termination = self._outcome()
        check_square = _square(board.king(board.turn)) if board.is_check() else None
        last = board.peek().uci() if board.move_stack else None
        return {
            "ok": True,
            "fen": board.fen(),
            "turn": "white" if board.turn == chess.WHITE else "black",
            "human_color": self._human_color,
            "elo": self._elo,
            "mode": self._mode,
            "fullmove_number": board.fullmove_number,
            "moves_uci": [m.uci() for m in board.move_stack],
            "moves_san": list(self._moves_san),
            "last_move": last,
            "in_check": board.is_check(),
            "check_square": check_square,
            "game_over": self._game_over(),
            "result": result,
            "termination": termination,
        }

    # -- push_move (section 3.4) -----------------------------------------------------------

    def push_move(self, uci: str) -> dict:
        no_game = self._require_game()
        if no_game:
            return no_game
        if self._game_over():
            return err("GAME_OVER", "the game has ended; no more moves accepted")
        if not isinstance(uci, str):
            return err("BAD_REQUEST", "move must be a UCI string")
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return err("BAD_REQUEST", f"{uci!r} is not a UCI move")
        if move not in self._board.legal_moves:
            return err("ILLEGAL_MOVE", f"{uci} is not legal in this position")
        san = self._board.san(move)
        self._board.push(move)
        self._moves_san.append(san)
        return {"ok": True, "san": san, "state": self.state()}

    # -- resign (section 3.8) --------------------------------------------------------------

    def resign(self, color: str) -> dict:
        no_game = self._require_game()
        if no_game:
            return no_game
        if color not in COLORS:
            return err("BAD_REQUEST", 'color must be "white" or "black"')
        # The other side wins.
        self._resignation = "0-1" if color == "white" else "1-0"
        return self.state()

    # -- move details for get_engine_move()/get_hint() (sections 3.5, 3.6) -----------------

    def _move_details(self, move: "chess.Move") -> dict:
        """Describe `move` in the current position for the LED/UI, before it is pushed."""
        board = self._board
        from_sq, to_sq = move.from_square, move.to_square
        rook_from = rook_to = None
        if board.is_castling(move):
            rank = chess.square_rank(from_sq)
            if board.is_kingside_castling(move):
                rook_from = chess.square(7, rank)  # h-file rook -> f-file
                rook_to = chess.square(5, rank)
            else:
                rook_from = chess.square(0, rank)  # a-file rook -> d-file
                rook_to = chess.square(3, rank)
        if board.is_en_passant(move):
            # The captured pawn sits on the destination file but the mover's starting rank.
            capture_square = _square(chess.square(chess.square_file(to_sq),
                                                   chess.square_rank(from_sq)))
        elif board.is_capture(move):
            capture_square = _square(to_sq)
        else:
            capture_square = None
        return {
            "ok": True,
            "move": move.uci(),
            "san": board.san(move),
            "from": _square(from_sq),
            "to": _square(to_sq),
            "rook_from": _square(rook_from) if rook_from is not None else None,
            "rook_to": _square(rook_to) if rook_to is not None else None,
            "capture_square": capture_square,
            "promotion": chess.piece_symbol(move.promotion) if move.promotion else None,
        }
