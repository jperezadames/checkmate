"""detect_move (contracts/interfaces.md section 2.5). Pure function, no hardware."""

import chess

from checkmate.camera.occupancy import changed_squares, occupancy_of_board, valid_occupancy
from checkmate.errors import err

PROMOTION_ORDER = "qrbn"


def detect_move(fen: str, occupancy: str) -> dict:
    """Work out which legal move from `fen` produces `occupancy`."""
    if not isinstance(fen, str):
        return err("BAD_REQUEST", "fen must be a string")
    if len(fen.split()) != 6:
        return err("BAD_REQUEST", "fen must be a full FEN (6 fields)")
    try:
        board = chess.Board(fen)
    except ValueError as e:
        return err("BAD_REQUEST", f"bad FEN: {e}")
    if not board.is_valid():
        return err("BAD_REQUEST", "fen is not a legal chess position")
    if not valid_occupancy(occupancy):
        return err("BAD_REQUEST", "occupancy must be 64 characters of W, B or .")

    before = occupancy_of_board(board)
    if occupancy == before:
        return {"ok": True, "status": "no_change"}

    matches = []
    for move in board.legal_moves:
        board.push(move)
        if occupancy_of_board(board) == occupancy:
            matches.append(move)
        board.pop()

    if len(matches) == 1:
        return {"ok": True, "status": "move", "move": matches[0].uci()}

    if matches and all(move.promotion for move in matches) and \
            len({(move.from_square, move.to_square) for move in matches}) == 1:
        first = matches[0]
        candidates = sorted((move.uci() for move in matches), key=lambda uci: PROMOTION_ORDER.index(uci[4]))
        return {
            "ok": True,
            "status": "promotion",
            "from": chess.square_name(first.from_square),
            "to": chess.square_name(first.to_square),
            "candidates": candidates,
        }

    return {"ok": True, "status": "invalid", "changed_squares": changed_squares(before, occupancy)}
