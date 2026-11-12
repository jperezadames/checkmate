"""Board geometry and colours for the LED matrix (contracts/interfaces.md sections 4.2, 4.3).

Moved here from the old Pico firmware: the Pi now drives the WS2812 matrix directly, so the Pi
owns the role -> colour table (4.2) and the square -> LED index mapping (4.3). Main still only
ever names squares and roles; colours live in one place here.
"""

FILES = "abcdefgh"
RANKS = "12345678"

# Section 4.2. Change colours here only; main sends role names, never colours.
ROLE_COLORS = {
    "engine_from": (0, 0, 255),   # blue
    "engine_to": (0, 255, 0),     # green
    "hint_from": (0, 255, 255),   # cyan
    "hint_to": (255, 255, 0),     # yellow
    "error": (255, 0, 0),         # red, blinks at 2 Hz (handled in controller.py)
    "check": (255, 128, 0),       # orange
    "last_move": (40, 40, 40),    # dim white
}

# self-test / boot: one corner per colour, so a mirrored or rotated panel is obvious.
TEST_STEPS = (("a1", (255, 0, 0)), ("h1", (0, 255, 0)), ("h8", (0, 0, 255)), ("a8", (255, 255, 255)))


class BoardLayout:
    """Maps a chess square to the 4 LED indices under it on a `size` x `size` matrix (2x2 LEDs
    per square). Index 0 is assumed at the a1 corner with the first row running along rank 1;
    `rotation` (0/90/180/270), `mirror` and `serpentine` cover the other ways a panel can be
    mounted. Use self_test() to find the right values."""

    def __init__(self, size=16, serpentine=True, rotation=0, mirror=False):
        self.size = size
        self.serpentine = serpentine
        self.rotation = rotation
        self.mirror = mirror
        self.num_leds = size * size

    def _physical_index(self, x, y):
        """Logical cell (x from the a-file side, y from the rank-1 side) -> strip index."""
        size = self.size
        for _ in range((self.rotation // 90) % 4):
            x, y = y, size - 1 - x
        if self.mirror:
            x = size - 1 - x
        if self.serpentine and y % 2 == 1:
            x = size - 1 - x
        return y * size + x

    def indices(self, square):
        """The 4 strip indices under a square like "e4"."""
        f = FILES.index(square[0])
        r = RANKS.index(square[1])
        x, y = 2 * f, 2 * r
        return [self._physical_index(x + dx, y + dy) for dy in (0, 1) for dx in (0, 1)]
