"""WebSocket /ws (contracts/interfaces.md section 5.1): `info` and `state` on connect, every
new `state` after that, and commands (5.5) from the UI. A rejected command gets a toast (5.6)."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from checkmate.errors import err

router = APIRouter()


@router.websocket("/ws")
async def websocket(ws: WebSocket):
    hub = ws.app.state.hub
    await ws.accept()
    out = hub.connect()
    sender = asyncio.create_task(_send_all(ws, out))
    try:
        while True:
            text = await ws.receive_text()
            try:
                problem = hub.submit(json.loads(text))
            except ValueError:
                problem = err("BAD_REQUEST", "a command must be JSON")
            if problem:
                out.put_nowait({"type": "toast", "level": "error", "text": problem["message"]})
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(out)
        sender.cancel()


async def _send_all(ws: WebSocket, out: asyncio.Queue):
    while True:
        await ws.send_json(await out.get())
