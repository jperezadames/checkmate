"""Create the FastAPI app: lifespan, CORS, routes, static UI files.

Skeleton only: the game loop and most endpoints are not implemented yet.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from checkmate.config import DEFAULT_PATH, load_config
from checkmate.server import api

REPO_ROOT = Path(__file__).resolve().parents[2]

config = load_config(DEFAULT_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: create Camera / GameEngine / LedController and start the game loop thread (section 6).
    yield
    # TODO: stop the game loop thread and close() every module.


app = FastAPI(title="CheckMate", lifespan=lifespan)

# Frontend dev server (Vite) on a laptop.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)

# TODO (section 5.1): WS /ws (in ws.py)

# Mounted last so it doesn't shadow the /api routes.
static_dir = REPO_ROOT / config["server"]["static_dir"]
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
