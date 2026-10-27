"""LED, Pi side (owner: Hsin-Chen). Contract: contracts/interfaces.md section 4.

Files:
    controller.py  LedController: serial JSON-lines protocol to the Pico (sections 4.1, 4.3)
    fake.py        FakeLedController: prints an 8x8 text grid (section 4.4)
    squares.py     role names and the check of show()'s argument (sections 4.1, 4.2)
"""

from checkmate.led.controller import LedController
from checkmate.led.fake import FakeLedController

__all__ = ["FakeLedController", "LedController"]
