"""Load config.json (interfaces.md 1.6). Each module only reads its own section."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = REPO_ROOT / "config.json"


def load_config(path=DEFAULT_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
