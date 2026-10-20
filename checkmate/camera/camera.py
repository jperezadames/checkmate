"""Camera class (contracts/interfaces.md sections 2.1 - 2.4)."""

import threading
import time

import cv2

from checkmate.camera import sources
from checkmate.camera.aruco import find_aruco_corners
from checkmate.camera.calibration import load_calibration, save_calibration
from checkmate.camera.motion import MotionDetector
from checkmate.camera.vision import analyze_frame, calibrate_from_frame, draw_debug
from checkmate.config import REPO_ROOT
from checkmate.errors import err

# No new frame for this long means the camera stopped: get_observation() returns
# CAMERA_NOT_READY, and start() reopens the camera (section 6, "retry").
FRAME_TIMEOUT_S = 2.0


def _frame_size(frame):
    h, w = frame.shape[:2]
    return [w, h]


def _stale(ts):
    return time.monotonic() - ts > FRAME_TIMEOUT_S


class Camera:
    def __init__(self, config: dict):
        if config.get("backend") not in sources.BACKENDS:
            raise ValueError(f"camera.backend must be one of {sources.BACKENDS}, got {config.get('backend')!r}")
        self.backend = config["backend"]
        self.device_index = int(config.get("device_index", 0))
        self.width = int(config.get("width", 1280))
        self.height = int(config.get("height", 720))
        # A relative path is relative to the repo root, like config.json.
        self.calibration_file = REPO_ROOT / config.get("calibration_file", "calibration.json")
        self.manual_corners = config.get("manual_corners")
        if self.manual_corners is not None and len(self.manual_corners) != 4:
            raise ValueError("camera.manual_corners must be 4 [x, y] points: a1, h1, h8, a8")

        self._lock = threading.Lock()
        self._motion = MotionDetector(float(config.get("stable_time_s", 0.5)))
        self._source = None
        self._thread = None
        self._stop = None
        self._calib = None
        self._frame = None
        self._frame_ts = 0.0
        self._warped = None
        self._obs = None
        self._seq = 0

    # -- lifecycle --------------------------------------------------------

    def start(self) -> dict:
        if self._thread is not None and self._thread.is_alive() and not _stale(self._frame_ts):
            return {"ok": True, "calibrated": self._calib is not None}
        # Not started yet, or the camera stopped sending frames: (re)open it.
        self.close()
        try:
            self._source = sources.open_source(self.backend, self.device_index, self.width, self.height)
        except Exception as e:
            return err("CAMERA_NOT_READY", f"cannot open camera ({self.backend}): {e}")
        with self._lock:
            self._calib = load_calibration(self.calibration_file)
            self._frame = self._warped = self._obs = None
            self._frame_ts = time.monotonic()  # counts as a frame, so the timeout starts now
            self._motion.reset()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(self._source, self._stop),
                                        name="camera", daemon=True)
        self._thread.start()
        return {"ok": True, "calibrated": self._calib is not None}

    def close(self) -> None:
        if self._thread is not None:
            self._stop.set()
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

    def calibrate(self) -> dict:
        try:
            with self._lock:
                frame = self._frame
                fresh = self._thread is not None and frame is not None and not _stale(self._frame_ts)
            if not fresh:
                return err("CAMERA_NOT_READY", "no frame from the camera")

            if self.manual_corners is not None:
                corners = self.manual_corners
            else:
                corners = find_aruco_corners(frame)
                if corners is None:
                    return err("CALIBRATION_FAILED", "could not find all 4 ArUco markers (ids 0-3)")

            calib = calibrate_from_frame(frame, corners)
            if calib is None:
                return err("CALIBRATION_FAILED",
                           "board not recognized; put the pieces in the starting position")

            saved = save_calibration(self.calibration_file, calib)
            with self._lock:
                self._calib = saved
                self._warped = self._obs = None
                self._motion.reset()
            return {
                "ok": True,
                "corners_px": calib["corners_px"],
                "frame_size": calib["frame_size"],
                "occupancy": calib["occupancy"],
            }
        except Exception as e:
            return err("CALIBRATION_FAILED", str(e))

    # -- background thread ------------------------------------------------

    def _run(self, source, stop):
        # `source` and `stop` belong to this thread, so a thread that close() gave up waiting
        # for can never read from the camera that start() opens next.
        while not stop.is_set():
            try:
                frame = source.read()
            except Exception:
                frame = None
            if stop.is_set():
                break
            if frame is None:
                time.sleep(0.05)
                continue
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            ts = time.monotonic()

            with self._lock:
                self._frame, self._frame_ts = frame, ts
                calib = self._calib
            if calib is None or _frame_size(frame) != calib["frame_size"]:
                continue

            try:
                warped, occupancy, low_confidence = analyze_frame(frame, calib)
            except Exception:
                continue

            with self._lock:
                if self._calib is not calib:  # recalibrated while this frame was analyzed
                    continue
                self._seq += 1
                self._warped = warped
                self._obs = {
                    "ok": True,
                    "ts": ts,
                    "seq": self._seq,
                    "stable": self._motion.update(warped, ts),
                    "occupancy": occupancy,
                    "low_confidence": low_confidence,
                }

    # -- observations -----------------------------------------------------

    def get_observation(self) -> dict:
        with self._lock:
            problem = self._not_ready()
            if problem:
                return err("CAMERA_NOT_READY", problem)
            obs = dict(self._obs)
        obs["low_confidence"] = list(obs["low_confidence"])
        return obs

    def _not_ready(self):
        """Why there is no observation to return, or None. Call with the lock held."""
        if self._thread is None:
            return "camera not started"
        if self._calib is None:
            return "camera not calibrated"
        if self._frame is not None and _frame_size(self._frame) != self._calib["frame_size"]:
            cw, ch = self._calib["frame_size"]
            fw, fh = _frame_size(self._frame)
            return f"calibrated at {cw}x{ch} but the camera gives {fw}x{fh}; calibrate again"
        if self._obs is None:
            return "no frame processed yet"
        if _stale(self._obs["ts"]):
            return f"no frames from the camera for {FRAME_TIMEOUT_S:g} s"
        return None

    def get_debug_image(self):
        """JPEG of the warped board with the grid and detections; raw frame if not calibrated."""
        try:
            with self._lock:
                if self._warped is not None and self._obs is not None:
                    img = draw_debug(self._warped, self._obs["occupancy"], self._obs["low_confidence"])
                elif self._frame is not None:
                    img = self._frame
                else:
                    return None
            ok, buf = cv2.imencode(".jpg", img)
            return buf.tobytes() if ok else None
        except Exception:
            return None
