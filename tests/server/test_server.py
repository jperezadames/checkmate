"""The whole backend with fake modules (section 5.7): routes, WebSocket and the game loop thread."""

import time

import pytest
from fastapi.testclient import TestClient

from checkmate.camera import START_FEN
from checkmate.config import load_config
from checkmate.server.app import create_app, parse_fakes

START = {"type": "start_game", "human_color": "white", "elo": 1500, "mode": "play"}


@pytest.fixture
def client():
    with TestClient(create_app(load_config(), fakes=parse_fakes("all"))) as client:
        wait_for(client, "idle")
        yield client


def wait_for(client, phase, timeout=5.0):
    """The state once the loop thread reaches `phase`."""
    deadline = time.monotonic() + timeout
    while True:
        r = client.get("/api/state")
        if r.status_code == 200 and r.json()["phase"] == phase:
            return r.json()
        assert time.monotonic() < deadline, f"still {r.json()} instead of {phase}"
        time.sleep(0.02)


def receive_until(ws, phase):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "state" and msg["phase"] == phase:
            return msg


def test_health_info_state(client):
    assert client.get("/api/health").json() == {
        "ok": True, "devices": {"camera": "ok", "engine": "ok", "led": "ok"}}
    assert client.get("/api/info").json()["engine_name"] == "FakeGameEngine"
    assert client.get("/api/state").json()["type"] == "state"


def test_websocket_sends_info_then_state(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "info"
        assert ws.receive_json()["phase"] == "idle"


def test_play_a_move_over_http(client):
    assert client.post("/api/command", json=START).json() == {"ok": True}
    wait_for(client, "human_turn")  # the fake board starts in the start position
    assert client.post("/api/fake/board", json={"move": "e2e4"}).status_code == 200
    state = wait_for(client, "engine_move_pending")
    assert state["moves_san"] == ["e4"]
    assert state["rating"]["played"] == "e2e4"

    client.post("/api/fake/board", json={"move": state["engine_move"]["move"]})
    state = wait_for(client, "human_turn")
    assert len(state["moves_san"]) == 2


def test_commands_over_websocket(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(START)
        state = receive_until(ws, "human_turn")
        assert state["human_color"] == "white"

        ws.send_json({"type": "promote", "piece": "q"})
        toast = ws.receive_json()
        assert toast["type"] == "toast" and toast["level"] == "error"

        ws.send_text("not json")
        assert ws.receive_json()["type"] == "toast"

        ws.send_json({"type": "resign"})
        assert receive_until(ws, "game_over")["termination"] == "RESIGNATION"


def test_rejected_commands_over_http(client):
    r = client.post("/api/command", json={"type": "hint"})
    assert r.status_code == 400 and r.json()["error"] == "NOT_ALLOWED"
    r = client.post("/api/command", json={"type": "start_game", "human_color": "white"})
    assert r.status_code == 400 and r.json()["error"] == "BAD_REQUEST"
    r = client.post("/api/command", content=b"{oops")
    assert r.status_code == 400 and r.json()["error"] == "BAD_REQUEST"


def test_wrong_board_then_fixed(client):
    client.post("/api/fake/board", json={"occupancy": "." * 64})
    client.post("/api/command", json=START)
    state = wait_for(client, "setup_check")
    assert len(state["board_problem"]["squares"]) == 32
    client.post("/api/fake/board", json={"fen": START_FEN})
    wait_for(client, "human_turn")


def test_fake_board_checks_its_input(client):
    assert client.post("/api/fake/board", json={"move": "e2e4"}).json()["error"] == "NO_GAME"
    client.post("/api/command", json=START)
    wait_for(client, "human_turn")
    assert client.post("/api/fake/board", json={"move": "e2e5"}).json()["error"] == "ILLEGAL_MOVE"
    assert client.post("/api/fake/board", json={"occupancy": "W"}).json()["error"] == "BAD_REQUEST"
    assert client.post("/api/fake/board", json={"stable": False}).json()["stable"] is False


def test_fake_lists_the_fake_modules(client):
    assert client.get("/api/fake").json() == {"ok": True, "modules": ["camera", "engine", "led"]}


def test_fake_state_is_broadcast_as_is(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.receive_json()
        client.post("/api/fake/state", json={"phase": "promotion_choice", "message": "demo"})
        assert ws.receive_json() == {"type": "state", "phase": "promotion_choice", "message": "demo"}


def test_camera_jpg_is_404_without_an_image(client):
    assert client.get("/api/camera.jpg").status_code == 404


def test_fake_routes_only_with_fakes():
    app = create_app(load_config())
    assert not any(getattr(route, "path", "").startswith("/api/fake") for route in app.routes)


def test_parse_fakes():
    assert parse_fakes("") == set()
    assert parse_fakes("all") == {"camera", "engine", "led"}
    assert parse_fakes(" camera, led ") == {"camera", "led"}
    with pytest.raises(ValueError):
        parse_fakes("camera,screen")
