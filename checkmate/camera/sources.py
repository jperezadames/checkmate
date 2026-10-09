"""Frame sources: each has read() -> BGR numpy image (or None) and close()."""

import time

import cv2


class Picamera2Source:
    def __init__(self, width, height):
        from picamera2 import Picamera2  # only available on the Pi (apt install python3-picamera2)

        self.cam = Picamera2()
        # "RGB888" is B, G, R in memory: what OpenCV expects (section 2.8).
        cfg = self.cam.create_video_configuration(main={"size": (width, height), "format": "RGB888"})
        self.cam.configure(cfg)
        self.cam.start()
        time.sleep(1.0)  # let auto exposure / white balance settle
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

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self):
        self.cap.release()
