"""Create the FastAPI app (contracts/interfaces.md section 5.1): the modules and the game loop
thread, the routes, the UI's built files.

Environment variables:
    CHECKMATE_CONFIG  another config file instead of config.json in the repo root
    CHECKMATE_FAKE    modules to replace with their fakes: "all", or some of "camera,engine,led"
                      (also mounts the debug routes /api/fake/*, see fake.py)
"""

import asyncio
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from checkmate.camera import Camera, FakeCamera
from checkmate.config import DEFAULT_PATH, REPO_ROOT, load_config
from checkmate.engine import FakeGameEngine, GameEngine
from checkmate.game import run_game_loop
from checkmate.led import FakeLedController, LedController
from checkmate.server import api, fake, ws
from checkmate.server.hub import Hub

# name -> (real class, fake class); each gets its own config section (section 1.6)
MODULES = {
    "camera": (Camera, FakeCamera),
    "engine": (GameEngine, FakeGameEngine),
    "led": (LedController, FakeLedController),
}
SHUTDOWN_TIMEOUT_S = 10.0  # the loop may be in the middle of calibrate() (up to 5 s)


def parse_fakes(text: str) -> set:
    """CHECKMATE_FAKE -> the set of module names to fake."""
    names = {name.strip() for name in text.split(",") if name.strip()}
    if "all" in names:
        return set(MODULES)
    unknown = names - set(MODULES)
    if unknown:
        raise ValueError(f"CHECKMATE_FAKE: unknown module {', '.join(sorted(unknown))}; "
                         f"use all, or some of {', '.join(MODULES)}")
    return names


def create_app(config: dict, fakes=frozenset()) -> FastAPI:
    hub = Hub()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if fakes:
            print(f"[server] fake modules: {', '.join(sorted(fakes))}", flush=True)
        camera, engine, led = (MODULES[name][name in fakes](config[name]) for name in MODULES)
        app.state.camera = camera  # for /api/fake/board only; nothing else touches it
        hub.loop = asyncio.get_running_loop()
        stop = threading.Event()
        thread = threading.Thread(target=run_game_loop, name="game", daemon=True,
                                  args=(camera, engine, led, hub.commands, hub.publish, stop))
        thread.start()
        try:
            yield
        finally:
            stop.set()
            await asyncio.to_thread(thread.join, SHUTDOWN_TIMEOUT_S)
            hub.loop = None

    app = FastAPI(title="CheckMate", lifespan=lifespan)
    app.state.hub = hub
    app.state.fakes = sorted(fakes)  # for GET /api/fake

    # Frontend dev server (Vite) on a laptop; `npm run dev` serves it on 127.0.0.1.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api.router)
    app.include_router(ws.router)
    if fakes:
        app.include_router(fake.router)

    # Mounted last so it doesn't shadow the /api routes.
    static_dir = REPO_ROOT / config["server"]["static_dir"]
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
    return app


app = create_app(load_config(os.environ.get("CHECKMATE_CONFIG", DEFAULT_PATH)),
                 parse_fakes(os.environ.get("CHECKMATE_FAKE", "")))
