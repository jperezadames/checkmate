"""FakeLedController (contracts/interfaces.md section 4.4): same methods as LedController, no
hardware. Always returns {"ok": True} and prints what would be lit as an 8x8 grid, rank 8 on
top. A bad show() argument is printed as a warning, so mistakes still show up."""

from checkmate.led.squares import FILES, RANKS, check_squares

ROLE_CHARS = {"engine_from": "F", "engine_to": "T", "hint_from": "f", "hint_to": "t",
              "error": "X", "check": "C", "last_move": "L"}


def render_grid(squares: list) -> str:
    roles = {item["sq"]: item["role"] for item in squares}
    lines = ["  " + " ".join(FILES)]
    for rank in reversed(RANKS):
        lines.append(rank + " " + " ".join(ROLE_CHARS[roles[f + rank]] if f + rank in roles else "."
                                           for f in FILES))
    used = [role for role in ROLE_CHARS if role in roles.values()]
    if used:
        lines.append("  " + ", ".join(f"{ROLE_CHARS[role]} {role}" for role in used))
    return "\n".join(lines)


class FakeLedController:
    def __init__(self, config: dict = None):
        pass

    def start(self) -> dict:
        return {"ok": True, "fw": "fake"}

    def close(self) -> None:
        pass

    def show(self, squares: list) -> dict:
        problem = check_squares(squares)
        if problem:
            print(f"[fake LED] warning, the real board would return BAD_REQUEST: {problem}", flush=True)
        else:
            print("[fake LED]\n" + render_grid(squares), flush=True)
        return {"ok": True}

    def clear(self) -> dict:
        print("[fake LED] clear", flush=True)
        return {"ok": True}

    def set_brightness(self, percent: int) -> dict:
        print(f"[fake LED] brightness {percent}%", flush=True)
        return {"ok": True}

    def self_test(self) -> dict:
        print("[fake LED] self test: a1, h1, h8, a8", flush=True)
        return {"ok": True}

    def is_connected(self) -> bool:
        return True
