"""detect_move (contracts/interfaces.md section 2.5). Pure function, no hardware."""

import chess

from checkmate.camera.occupancy import changed_squares, occupancy_of_board, valid_occupancy
from checkmate.errors import err

PROMOTION_ORDER = "qrbn"


def detect_move(fen: str, occupancy: str) -> dict:
    """Work out which legal move from `fen` produces `occupancy`."""
    if not isinstance(fen, str):
        return err("BAD_REQUEST", "fen must be a string")
    try:
        board = chess.Board(fen)
    except ValueError as e:
        return err("BAD_REQUEST", f"bad FEN: {e}")
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

    if matches and all(m.promotion for m in matches) and \
            len({(m.from_square, m.to_square) for m in matches}) == 1:
        m = matches[0]
        candidates = sorted((x.uci() for x in matches), key=lambda u: PROMOTION_ORDER.index(u[4]))
        return {
            "ok": True,
            "status": "promotion",
            "from": chess.square_name(m.from_square),
            "to": chess.square_name(m.to_square),
            "candidates": candidates,
        }

    return {"ok": True, "status": "invalid", "changed_squares": changed_squares(before, occupancy)}
