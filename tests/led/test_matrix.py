"""Board geometry and colours (contracts/interfaces.md sections 4.2, 4.3)."""

from checkmate.led.matrix import ROLE_COLORS, BoardLayout


def test_roles_have_colours():
    assert set(ROLE_COLORS) == {
        "engine_from", "engine_to", "hint_from", "hint_to", "error", "check", "last_move"
    }
    assert all(len(c) == 3 and all(0 <= v <= 255 for v in c) for c in ROLE_COLORS.values())


def test_square_covers_four_distinct_in_range_leds():
    layout = BoardLayout(size=16)
    for square in ("a1", "e4", "h8"):
        idx = layout.indices(square)
        assert len(idx) == 4
        assert len(set(idx)) == 4
        assert all(0 <= i < 256 for i in idx)


def test_a1_corner_block():
    # Default mounting: index 0 at a1, first row along rank 1, serpentine wiring.
    # a1 covers cells (0,0),(1,0),(0,1),(1,1); row 0 straight, row 1 reversed.
    layout = BoardLayout(size=16, serpentine=True, rotation=0, mirror=False)
    assert set(layout.indices("a1")) == {0, 1, 30, 31}


def test_every_square_maps_to_unique_leds():
    layout = BoardLayout(size=16)
    seen = set()
    for f in "abcdefgh":
        for r in "12345678":
            idx = layout.indices(f + r)
            assert not (set(idx) & seen), f"{f}{r} overlaps another square"
            seen.update(idx)
    assert len(seen) == 256  # 64 squares x 4 LEDs fill the 16x16 matrix
