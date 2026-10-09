"""FastAPI backend (contracts/interfaces.md section 5.1).

Run with:
    uvicorn checkmate.server:app --host 127.0.0.1 --port 8000
"""

from checkmate.server.app import app

__all__ = ["app"]
