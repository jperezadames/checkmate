"""Command format and phase rules (sections 5.4, 5.5)."""

import pytest

from checkmate.game import check_command

START = {"type": "start_game", "human_color": "random", "elo": 1500, "mode": "practice"}


@pytest.mark.parametrize("cmd", [
    None,
    [],
    {"type": "jump"},
    dict(START, human_color="red"),
    dict(START, elo="1500"),
    dict(START, elo=True),
    dict(START, mode="blitz"),
    {"type": "promote", "piece": "k"},
    {"type": "promote"},
])
def test_bad_format(cmd):
    assert check_command(cmd, "idle")["error"] == "BAD_REQUEST"


@pytest.mark.parametrize("cmd, phase", [
    (START, "idle"),
    (START, "game_over"),
    ({"type": "calibrate"}, "error"),
    ({"type": "hint"}, "human_turn"),
    ({"type": "promote", "piece": "q"}, "promotion_choice"),
    ({"type": "resign"}, "engine_move_pending"),
    ({"type": "cancel"}, "setup_check"),
    ({"type": "retry"}, "error"),
])
def test_allowed(cmd, phase):
    assert check_command(cmd, phase) is None


@pytest.mark.parametrize("cmd, phase", [
    (START, "human_turn"),
    ({"type": "hint"}, "engine_thinking"),
    ({"type": "cancel"}, "calibrating"),
    ({"type": "resign"}, "setup_check"),
    ({"type": "retry"}, "idle"),
    ({"type": "hint"}, "starting"),
])
def test_not_allowed(cmd, phase):
    assert check_command(cmd, phase)["error"] == "NOT_ALLOWED"
