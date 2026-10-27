"""What main may ask the LED board to show (contracts/interfaces.md sections 4.1, 4.2).

A pattern is a list of {"sq": square, "role": role}. The Pico firmware owns the colors and
effects; the Pi only checks the names before sending them.
"""

FILES = "abcdefgh"
RANKS = "12345678"
ROLES = ("engine_from", "engine_to", "hint_from", "hint_to", "error", "check", "last_move")


def is_square(name) -> bool:
    return isinstance(name, str) and len(name) == 2 and name[0] in FILES and name[1] in RANKS


def check_squares(squares):
    """Error message if `squares` is not a valid show() argument, else None."""
    if not isinstance(squares, list):
        return 'squares must be a list of {"sq": square, "role": role}'
    seen = set()
    for item in squares:
        if not isinstance(item, dict) or "sq" not in item or "role" not in item:
            return f'bad item {item!r}; use {{"sq": square, "role": role}}'
        sq, role = item["sq"], item["role"]
        if not is_square(sq):
            return f"bad square {sq!r}"
        if role not in ROLES:
            return f"bad role {role!r} for {sq}; use one of {', '.join(ROLES)}"
        if sq in seen:
            return f"{sq} appears twice"
        seen.add(sq)
    return None
