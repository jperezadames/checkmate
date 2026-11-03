"""Debug routes for the fake backend (contracts/interfaces.md section 5.7). Only mounted when
some module is fake (CHECKMATE_FAKE).

GET  /api/fake         {"ok": true, "modules": [...]}: which modules are fake; the UI lets you
                       move pieces on its board when the camera is
POST /api/fake/state   body = a `state` object: broadcast as-is, to show any phase in the UI
POST /api/fake/board   what the FakeCamera sees (the camera must be fake):
    {"move": "e2e4"}       the position in `state.fen` after this move. Works for the
                           computer's move too: in engine_move_pending, `fen` is still the
                           position before it.
    {"fen": "<FEN>"}       that position, e.g. the start position before a new game
    {"occupancy": "..."}   64 chars of W B . (section 1.2), e.g. a wrong board
    {"stable": false}      a hand over the board; can be sent with any of the above
"""

import json

import chess
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from checkmate.camera import FakeCamera, occupancy_from_fen
from checkmate.errors import err

router = APIRouter(prefix="/api/fake")


def _bad(code, message):
    return JSONResponse(err(code, message), status_code=400)


async def _body(request: Request):
    try:
        body = json.loads(await request.body())
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


@router.get("")
async def fake_modules(request: Request):
    return {"ok": True, "modules": request.app.state.fakes}


@router.post("/state")
async def fake_state(request: Request):
    state = await _body(request)
    if state is None:
        return _bad("BAD_REQUEST", "the body must be a state object")
    request.app.state.hub.publish(dict(state, type="state"))
    return {"ok": True}


@router.post("/board")
async def fake_board(request: Request):
    camera = request.app.state.camera
    if not isinstance(camera, FakeCamera):
        return _bad("NOT_ALLOWED", "the camera is not fake (CHECKMATE_FAKE)")
    body = await _body(request)
    if body is None:
        return _bad("BAD_REQUEST", "the body must be a JSON object")

    occupancy = camera.occupancy
    if "move" in body:
        state = request.app.state.hub.state
        if not state or not state["fen"]:
            return _bad("NO_GAME", "no game, so no position to play the move from")
        board = chess.Board(state["fen"])
        try:
            move = chess.Move.from_uci(str(body["move"]))
        except ValueError:
            return _bad("BAD_REQUEST", f"{body['move']!r} is not a UCI move")
        if move not in board.legal_moves:
            return _bad("ILLEGAL_MOVE", f"{move.uci()} is not legal in {state['fen']}")
        board.push(move)
        occupancy = occupancy_from_fen(board.fen())
    elif "fen" in body:
        try:
            occupancy = occupancy_from_fen(str(body["fen"]))
        except ValueError as e:
            return _bad("BAD_REQUEST", f"bad FEN: {e}")
    elif "occupancy" in body:
        occupancy = body["occupancy"]
        if not isinstance(occupancy, str) or len(occupancy) != 64 or not set(occupancy) <= set("WB."):
            return _bad("BAD_REQUEST", "occupancy must be 64 characters of W, B or .")

    camera.occupancy = occupancy  # a plain attribute, like the tests set it (section 2.7)
    if "stable" in body:
        camera.stable = bool(body["stable"])
    return {"ok": True, "occupancy": camera.occupancy, "stable": camera.stable}
