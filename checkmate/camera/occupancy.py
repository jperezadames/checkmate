"""Occupancy strings (contracts/interfaces.md sections 1.2, 1.4).

64 chars in python-chess square order a1, b1, ..., h1, a2, ..., h8:
"W" = white piece, "B" = black piece, "." = empty.
"""

import chess

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def occupancy_of_board(board: chess.Board) -> str:
    chars = []
    for sq in chess.SQUARES:
        color = board.color_at(sq)
        if color is None:
            chars.append(".")
        elif color == chess.WHITE:
            chars.append("W")
        else:
            chars.append("B")
    return "".join(chars)


def occupancy_from_fen(fen: str) -> str:
    """FEN -> 64-char occupancy string. Raises ValueError on a bad FEN."""
    return occupancy_of_board(chess.Board(fen))


def valid_occupancy(occupancy) -> bool:
    return isinstance(occupancy, str) and len(occupancy) == 64 and set(occupancy) <= set("WB.")


def changed_squares(a: str, b: str) -> list:
    """Names of the squares that differ between two occupancy strings, in a1..h8 order."""
    return [chess.square_name(i) for i in range(64) if a[i] != b[i]]
