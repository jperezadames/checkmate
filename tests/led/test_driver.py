"""WS2812-over-SPI encoding (contracts/interfaces.md section 4.3)."""

from checkmate.led.driver import RESET_BYTES, _TABLE, Ws2812Spi


class FakeSpi:
    def __init__(self):
        self.writes = []

    def writebytes2(self, data):
        self.writes.append(bytes(data))

    def close(self):
        pass


def test_bit_patterns():
    # 0 bit -> 100, 1 bit -> 110, 3 SPI bits per WS2812 bit, 3 bytes per colour byte.
    assert _TABLE[0x00] == bytes([0b10010010, 0b01001001, 0b00100100])
    assert _TABLE[0xFF] == bytes([0b11011011, 0b01101101, 0b10110110])
    assert len(_TABLE) == 256 and all(len(p) == 3 for p in _TABLE)


def test_write_uses_grb_order_and_reset():
    spi = FakeSpi()
    Ws2812Spi(spi).write([(1, 2, 3)])  # r=1, g=2, b=3
    buf = spi.writes[0]
    assert buf[0:3] == _TABLE[2]   # green first
    assert buf[3:6] == _TABLE[1]   # then red
    assert buf[6:9] == _TABLE[3]   # then blue
    assert buf[9:] == bytes(RESET_BYTES)  # trailing latch


def test_frame_length_for_full_matrix():
    spi = FakeSpi()
    Ws2812Spi(spi).write([(0, 0, 0)] * 256)
    assert len(spi.writes[0]) == 256 * 9 + RESET_BYTES


def test_writebytes_fallback_when_no_writebytes2():
    class OldSpi:
        def __init__(self):
            self.data = None

        def writebytes(self, data):
            self.data = data
    spi = OldSpi()
    Ws2812Spi(spi).write([(5, 6, 7)])
    assert isinstance(spi.data, list) and len(spi.data) == 9 + RESET_BYTES
