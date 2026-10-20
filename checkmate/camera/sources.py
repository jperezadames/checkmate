"""Frame sources: each has read() -> BGR numpy image (or None) and close()."""

import time

import cv2

BACKENDS = ("picamera2", "v4l2")

# Seconds of auto exposure / white balance before they are locked (section 2.8).
WARMUP_S = 1.0


def open_source(backend, device_index, width, height):
    if backend == "picamera2":
        return Picamera2Source(width, height)
    return V4l2Source(device_index, width, height)


class Picamera2Source:
    def __init__(self, width, height):
        from picamera2 import Picamera2  # only available on the Pi (apt install python3-picamera2)

        self.cam = Picamera2()
        # "RGB888" is B, G, R in memory: what OpenCV expects (section 2.8).
        cfg = self.cam.create_video_configuration(main={"size": (width, height), "format": "RGB888"})
        self.cam.configure(cfg)
        self.cam.start()
        time.sleep(WARMUP_S)
        self.cam.set_controls({"AeEnable": False, "AwbEnable": False})

    def read(self):
        return self.cam.capture_array()

    def close(self):
        self.cam.stop()
        self.cam.close()


class V4l2Source:
    def __init__(self, device_index, width, height):
        self.cap = cv2.VideoCapture(device_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open /dev/video{device_index}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._lock_exposure()

    def _lock_exposure(self):
        """Let auto exposure / white balance settle, then keep their current values (section 2.8).

        Best effort: a webcam without these controls ignores the calls.
        """
        end = time.monotonic() + WARMUP_S
        while time.monotonic() < end:
            self.cap.read()
        exposure = self.cap.get(cv2.CAP_PROP_EXPOSURE)
        wb_temperature = self.cap.get(cv2.CAP_PROP_WB_TEMPERATURE)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # V4L2 value 1 = manual exposure
        if exposure > 0:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
        self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        if wb_temperature > 0:
            self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, wb_temperature)

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self):
        self.cap.release()
