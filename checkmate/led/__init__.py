"""LED, Pi side (owner: Hsin-Chen). Contract: contracts/interfaces.md section 4.

The Pi drives the WS2812 matrix directly over SPI -- there is no Pico.

Files:
    controller.py  LedController: render thread + SPI output (sections 4.1, 4.3)
    driver.py      Ws2812Spi: WS2812-over-SPI encoding and output
    matrix.py      role -> colour table and square -> LED mapping (sections 4.2, 4.3)
    fake.py        FakeLedController: prints an 8x8 text grid (section 4.4)
    squares.py     role names and the check of show()'s argument (sections 4.1, 4.2)
"""

from checkmate.led.controller import LedController
from checkmate.led.fake import FakeLedController

__all__ = ["FakeLedController", "LedController"]
