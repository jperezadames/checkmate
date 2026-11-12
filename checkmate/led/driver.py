"""Drive a WS2812 (NeoPixel) matrix from the Raspberry Pi over SPI (contracts/interfaces.md 4.3).

Why SPI: the Raspberry Pi 5's RP1 I/O controller broke the old PWM/DMA libraries (rpi_ws281x /
Adafruit NeoPixel on GPIO18), so on a Pi 5 the data line goes on the **SPI MOSI pin
(GPIO10, physical pin 19)**. Each WS2812 bit is sent as 3 SPI bits -- a 1 is `110`, a 0 is
`100` -- so at ~2.4 MHz one WS2812 bit is ~0.42 us total with the ~0.4 us / ~0.8 us high time
WS2812 expects. A 3.3 V -> 5 V level shifter on the data line and an external 5 V supply for the
strip are still required (section 4.3 power note).

The SPI device is opened through open_spi(), kept separate so tests can supply a fake.
"""


def _expand(value: int) -> bytes:
    """One colour byte -> 24 SPI bits (3 bytes): each WS2812 bit becomes 110 (1) or 100 (0)."""
    bits = 0
    for i in range(8):
        bits = (bits << 3) | (0b110 if (value >> (7 - i)) & 1 else 0b100)
    return bytes(((bits >> 16) & 0xFF, (bits >> 8) & 0xFF, bits & 0xFF))


_TABLE = [_expand(v) for v in range(256)]
RESET_BYTES = 40  # low time after the frame to latch it (>50 us at 2.4 MHz)


def open_spi(bus: int, device: int, hz: int):
    """Open /dev/spidev<bus>.<device> for WS2812 output. Separate so tests can replace it."""
    import spidev  # Linux only; see requirements.txt

    spi = spidev.SpiDev()
    spi.open(bus, device)
    spi.max_speed_hz = hz
    spi.mode = 0
    return spi


class Ws2812Spi:
    """Encodes RGB pixels as a WS2812-over-SPI frame and writes them. `spi` is a spidev.SpiDev
    (or a fake exposing writebytes2/writebytes/close in tests)."""

    def __init__(self, spi):
        self._spi = spi

    def write(self, pixels) -> None:
        """pixels: list of (r, g, b) already scaled to the brightness to show. WS2812 takes the
        colour bytes in G, R, B order."""
        buf = bytearray()
        for r, g, b in pixels:
            buf += _TABLE[g & 0xFF]
            buf += _TABLE[r & 0xFF]
            buf += _TABLE[b & 0xFF]
        buf += bytes(RESET_BYTES)
        writer = getattr(self._spi, "writebytes2", None)
        if writer is not None:
            writer(bytes(buf))
        else:
            self._spi.writebytes(list(buf))

    def close(self) -> None:
        try:
            self._spi.close()
        except Exception:
            pass
