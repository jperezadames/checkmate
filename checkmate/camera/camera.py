"""Camera class (contracts/interfaces.md sections 2.1 - 2.4)."""

import json
import os
import threading
import time

import cv2
import numpy as np

from checkmate.camera import sources
from checkmate.camera.aruco import find_aruco_corners
from checkmate.camera.vision import analyze_frame, calibrate_from_frame, draw_debug
from checkmate.errors import err

# Mean absolute grayscale difference (0-255) between frames that counts as motion.
MOTION_THRESHOLD = 4.0


class Camera:
    def __init__(self, config: dict):
        if config.get("backend") not in ("picamera2", "v4l2"):
            raise ValueError(f"camera.backend must be 'picamera2' or 'v4l2', got {config.get('backend')!r}")
        self.backend = config["backend"]
        self.device_index = int(config.get("device_index", 0))
        self.width = int(config.get("width", 1280))
        self.height = int(config.get("height", 720))
        self.calibration_file = config.get("calibration_file", "calibration.json")
        self.stable_time_s = float(config.get("stable_time_s", 0.5))
        self.manual_corners = config.get("manual_corners")
        self.aruco_dict = config.get("aruco_dict", "DICT_4X4_50")
        if self.manual_corners is not None and len(self.manual_corners) != 4:
            raise ValueError("camera.manual_corners must be 4 [x, y] points: a1, h1, h8, a8")

        self._lock = threading.Lock()
        self._source = None
        self._thread = None
        self._running = False
        self._calib = None
        self._frame = None
        self._warped = None
        self._obs = None
        self._seq = 0
        self._prev_small = None
        self._last_motion = 0.0

    # -- lifecycle --------------------------------------------------------

    def start(self) -> dict:
        try:
            if self._running:
                return {"ok": True, "calibrated": self._calib is not None}
            if self.backend == "picamera2":
                self._source = sources.Picamera2Source(self.width, self.height)
            else:
                self._source = sources.V4l2Source(self.device_index, self.width, self.height)
            self._calib = self._load_calibration()
            self._last_motion = time.monotonic()
            self._running = True
            self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
            self._thread.start()
            return {"ok": True, "calibrated": self._calib is not None}
        except Exception as e:
            self._release_source()
            return err("CAMERA_NOT_READY", f"cannot open camera ({self.backend}): {e}")

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._release_source()

    def _release_source(self):
        if self._source is not None:
            try:
                self._source.close()
            except Exception:
                pass
            self._source = None

    # -- calibration ------------------------------------------------------

    def _load_calibration(self):
        if not os.path.exists(self.calibration_file):
            return None
        with open(self.calibration_file, encoding="utf-8") as f:
            calib = json.load(f)
        # Calibration made at a different resolution: scale the corners.
        fw, fh = calib["frame_size"]
        if (fw, fh) != (self.width, self.height):
            sx, sy = self.width / fw, self.height / fh
            calib["corners_px"] = [[x * sx, y * sy] for x, y in calib["corners_px"]]
            calib["frame_size"] = [self.width, self.height]
        return calib

    def calibrate(self) -> dict:
        try:
            with self._lock:
                frame = None if self._frame is None else self._frame.copy()
            if frame is None:
                return err("CAMERA_NOT_READY", "no frame from the camera yet")

            if self.manual_corners is not None:
                corners = self.manual_corners
            else:
                corners = find_aruco_corners(frame, self.aruco_dict)
                if corners is None:
                    return err("CALIBRATION_FAILED", "could not find all 4 ArUco markers (ids 0-3)")

            calib = calibrate_from_frame(frame, corners)
            if calib is None:
                return err("CALIBRATION_FAILED",
                           "board not recognized; put the pieces in the starting position")

            saved = {k: calib[k] for k in ("corners_px", "frame_size", "centroids")}
            with open(self.calibration_file, "w", encoding="utf-8") as f:
                json.dump(saved, f, indent=2)
            with self._lock:
                self._calib = saved
                self._prev_small = None
            return {
                "ok": True,
                "corners_px": calib["corners_px"],
                "frame_size": calib["frame_size"],
                "occupancy": calib["occupancy"],
            }
        except Exception as e:
            return err("CALIBRATION_FAILED", str(e))

    # -- background thread ------------------------------------------------

    def _run(self):
        while self._running:
            try:
                frame = self._source.read()
            except Exception:
                frame = None
            if frame is None:
                time.sleep(0.05)
                continue
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            ts = time.monotonic()

            with self._lock:
                self._frame = frame
                calib = self._calib
            if calib is None:
                continue

            try:
                warped, occupancy, low = analyze_frame(frame, calib)
            except Exception:
                continue
            stable = self._update_motion(warped, ts)

            with self._lock:
                self._seq += 1
                self._warped = warped
                self._obs = {
                    "ok": True,
                    "ts": ts,
                    "seq": self._seq,
                    "stable": stable,
                    "occupancy": occupancy,
                    "low_confidence": low,
                }

    def _update_motion(self, warped, ts):
        small = cv2.resize(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (64, 64)).astype(np.float32)
        if self._prev_small is None or float(np.abs(small - self._prev_small).mean()) > MOTION_THRESHOLD:
            self._last_motion = ts
        self._prev_small = small
        return ts - self._last_motion >= self.stable_time_s

    # -- observations -----------------------------------------------------

    def get_observation(self) -> dict:
        if not self._running:
            return err("CAMERA_NOT_READY", "camera not started")
        with self._lock:
            if self._calib is None:
                return err("CAMERA_NOT_READY", "camera not calibrated")
            if self._obs is None:
                return err("CAMERA_NOT_READY", "no frame processed yet")
            obs = dict(self._obs)
        obs["low_confidence"] = list(obs["low_confidence"])
        return obs

    def get_debug_image(self):
        """JPEG of the warped board with the grid and detections; raw frame if not calibrated."""
        try:
            with self._lock:
                if self._warped is not None and self._obs is not None:
                    img = draw_debug(self._warped, self._obs["occupancy"], self._obs["low_confidence"])
                elif self._frame is not None:
                    img = self._frame.copy()
                else:
                    return None
            ok, buf = cv2.imencode(".jpg", img)
            return buf.tobytes() if ok else None
        except Exception:
            return None
