"""MotionDetector on synthetic warped boards."""

import numpy as np

from checkmate.camera.motion import MotionDetector
from checkmate.camera.vision import warp_board
from tests.camera.synthetic import START_OCC, expected_corners, render


def _warped(**kwargs):
    return warp_board(render(START_OCC, **kwargs), expected_corners())


def _feed(detector, frames, start=0.0, step=0.1):
    return [detector.update(frame, start + k * step) for k, frame in enumerate(frames)]


def test_still_board_becomes_stable():
    board = _warped()
    assert _feed(MotionDetector(0.5), [board] * 7) == [False] * 5 + [True] * 2


def test_hand_over_a_few_squares_is_motion():
    board, hand = _warped(), _warped(hand=True)
    detector = MotionDetector(0.5)
    assert _feed(detector, [board] * 6)[-1] is True
    assert detector.update(hand, 0.6) is False


def test_camera_noise_is_not_motion():
    rng = np.random.default_rng(0)
    board = _warped().astype(np.float32)
    noisy = [np.clip(board + rng.normal(0, 8, board.shape), 0, 255).astype(np.uint8) for _ in range(7)]
    assert _feed(MotionDetector(0.5), noisy)[-1] is True


def test_reset_counts_next_frame_as_motion():
    board = _warped()
    detector = MotionDetector(0.5)
    assert _feed(detector, [board] * 6)[-1] is True
    detector.reset()
    assert detector.update(board, 0.6) is False
