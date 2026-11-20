"""LED, Pi side (owner: Hsin-Chen). Contract: contracts/interfaces.md section 4.

The Pico drives the matrix on D16 and reads the Grove controls on A0/D20.

Files:
    controller.py  LedController: shared USB serial link, controls, and LED commands
    matrix.py      geometry/colours shared with the MicroPython firmware
    fake.py        FakeLedController: prints an 8x8 text grid (section 4.4)
    squares.py     role names and the check of show()'s argument (sections 4.1, 4.2)
"""

from checkmate.led.controller import LedController
from checkmate.led.fake import FakeLedController

__all__ = ["FakeLedController", "LedController"]
