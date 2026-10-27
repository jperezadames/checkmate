"""What the LED board shows: square names -> roles -> colors. Pure functions, no hardware.

A "frame" is a dict {square name: role}, e.g. {"e2": "from", "e4": "to"}. Squares that are not
in the frame are dark. LedController and FakeLedController both take frames.
"""

FILES = "abcdefgh"
RANKS = "12345678"

# RGB at full brightness; the Pico scales them by the configured brightness.
ROLE_COLORS = {
    "from": (0, 255, 0),       # green: pick the piece up here
    "to": (0, 90, 255),        # blue: put it down here
    "capture": (255, 0, 0),    # red: remove this piece (en passant)
    "problem": (255, 110, 0),  # orange: this square doesn't match the expected position
    "hint": (170, 0, 255),     # purple: hint squares
    "check": (255, 0, 120),    # pink: king in check
}

# One character per role for FakeLedController's text grid.
ROLE_CHARS = {"from": "F", "to": "T", "capture": "X", "problem": "!", "hint": "H", "check": "K"}


def is_square(name) -> bool:
    return isinstance(name, str) and len(name) == 2 and name[0] in FILES and name[1] in RANKS


def check_frame(frame):
    """Error message if `frame` is not a valid {square: role} dict, else None."""
    if not isinstance(frame, dict):
        return "squares must be a dict of square name -> role"
    for square, role in frame.items():
        if not is_square(square):
            return f"bad square name {square!r}"
        if role not in ROLE_COLORS:
            return f"bad role {role!r} for {square}; use one of {', '.join(ROLE_COLORS)}"
    return None


def move_frame(move: dict, role_from="from", role_to="to") -> dict:
    """Frame for a move dict (the state's engine_move / hint, section 5.3).

    Lights from/to, the rook's from/to when castling, and the captured pawn when it is not on
    the destination square (en passant). A normal capture just shows "to": the UI says to remove
    the captured piece.
    """
    frame = {}
    for key, role in (("from", role_from), ("to", role_to), ("rook_from", role_from), ("rook_to", role_to)):
        if move.get(key):
            frame[move[key]] = role
    capture = move.get("capture_square")
    if capture and capture not in frame:
        frame[capture] = "capture"
    return frame


def frame_colors(frame: dict) -> dict:
    """{square: [r, g, b]} as sent to the Pico."""
    return {square: list(ROLE_COLORS[role]) for square, role in frame.items()}


def render_grid(frame: dict) -> str:
    """8x8 text picture of a frame, rank 8 at the top, as seen from White."""
    lines = ["  " + " ".join(FILES)]
    for rank in reversed(RANKS):
        cells = [ROLE_CHARS.get(frame.get(f + rank), ".") for f in FILES]
        lines.append(rank + " " + " ".join(cells))
    return "\n".join(lines)
