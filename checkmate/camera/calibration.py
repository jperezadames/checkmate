"""Calibration file: what calibrate() saves and start() loads."""

import json

from checkmate.camera.vision import CLASSES

SAVED_KEYS = ("corners_px", "frame_size", "centroids")


def save_calibration(path, calib) -> dict:
    """Write the fields analyze_frame() needs to `path`; returns them."""
    saved = {k: calib[k] for k in SAVED_KEYS}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2)
    return saved


def load_calibration(path):
    """Saved calibration, or None if the file is missing, unreadable or from an older format.

    None makes start() report "calibrated": false, so main runs calibrate() and overwrites it.
    """
    try:
        with open(path, encoding="utf-8") as f:
            calib = json.load(f)
        _check(calib)
        return calib
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _check(calib):
    """Raise ValueError unless `calib` has the shape save_calibration() writes."""
    corners, size, centroids = (calib[k] for k in SAVED_KEYS)
    ok = (
        len(corners) == 4 and all(len(p) == 2 for p in corners)
        and len(size) == 2
        and all(len(centroids[shade][cls]) == 2 for shade in ("dark", "light") for cls in CLASSES)
    )
    if not ok:
        raise ValueError("calibration file has the wrong shape")
