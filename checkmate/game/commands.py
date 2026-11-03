"""UI commands (contracts/interfaces.md sections 5.4, 5.5): their format, and which phases
allow them. The server checks both before queueing a command, so /api/command can answer
400 at once; the game loop checks the phase again when it takes the command out."""

from checkmate.errors import err

ALLOWED = {
    "idle": {"start_game", "calibrate"},
    "calibrating": set(),
    "setup_check": {"cancel"},
    "human_turn": {"hint", "resign", "cancel"},
    "engine_thinking": {"resign", "cancel"},
    "engine_move_pending": {"resign", "cancel"},
    "promotion_choice": {"promote", "cancel"},
    "game_over": {"start_game", "cancel"},
    "error": {"retry", "calibrate", "cancel"},
}
TYPES = {"start_game", "hint", "promote", "resign", "cancel", "calibrate", "retry"}


def check_format(cmd):
    """BAD_REQUEST error if `cmd` is not a well-formed command (5.5), else None."""
    if not isinstance(cmd, dict) or cmd.get("type") not in TYPES:
        return err("BAD_REQUEST", f"unknown command; use one of {', '.join(sorted(TYPES))}")
    if cmd["type"] == "start_game":
        if cmd.get("human_color") not in ("white", "black", "random"):
            return err("BAD_REQUEST", 'human_color must be "white", "black" or "random"')
        elo = cmd.get("elo")
        if isinstance(elo, bool) or not isinstance(elo, int):
            return err("BAD_REQUEST", "elo must be an int")
        if cmd.get("mode") not in ("play", "practice"):
            return err("BAD_REQUEST", 'mode must be "play" or "practice"')
    if cmd["type"] == "promote" and cmd.get("piece") not in ("q", "r", "b", "n"):
        return err("BAD_REQUEST", 'piece must be "q", "r", "b" or "n"')
    return None


def check_phase(cmd: dict, phase: str):
    """NOT_ALLOWED error if a well-formed `cmd` can't be sent in `phase` (5.4), else None."""
    if cmd["type"] not in ALLOWED.get(phase, set()):
        return err("NOT_ALLOWED", f"{cmd['type']} is not available now ({phase})")
    return None


def check_command(cmd, phase: str):
    return check_format(cmd) or check_phase(cmd, phase)
