"""Load config.json (interfaces.md 1.6). Each module only reads its own section."""

import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config(path=DEFAULT_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
