"""Engine / game state (owner: Joel). Contract: contracts/interfaces.md section 3.

Files:
    base.py    BaseChessGame: shared board, state(), push_move(), resign(), move details
    engine.py  GameEngine: python-chess board + Stockfish (sections 3.1 - 3.8)
    fake.py    FakeGameEngine: no Stockfish (section 3.9)

Everything returned to main is a plain dict / str (section 0.2); no chess.Board crosses the
boundary. Public methods never raise; they return {"ok": False, "error": CODE, ...} instead
(the only exception is __init__, which may raise on bad config).
"""

from checkmate.engine.engine import GameEngine
from checkmate.engine.fake import FakeGameEngine

__all__ = ["GameEngine", "FakeGameEngine"]
