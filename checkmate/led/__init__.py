"""LED, Pi side (owner: Hsin-Chen). Contract: contracts/interfaces.md section 4.

Planned files:
    controller.py  LedController: serial JSON-lines protocol to the Pico (sections 4.1 - 4.3)
    fake.py        FakeLedController: prints an 8x8 text grid (section 4.4)

Re-export the public names here, e.g.:
    from checkmate.led.controller import LedController
    from checkmate.led.fake import FakeLedController
"""
from checkmate.led.controller import LedController
from checkmate.led.fake import FakeLedController
from checkmate.led.frames import ROLE_COLORS, move_frame

__all__ = ["ROLE_COLORS", "FakeLedController", "LedController", "move_frame"]
