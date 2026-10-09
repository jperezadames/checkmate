import pytest

from checkmate.camera import START_FEN, occupancy_from_fen


def test_start_position():
    assert occupancy_from_fen(START_FEN) == "W" * 16 + "." * 32 + "B" * 16


def test_index_order_is_a1_to_h8():
    occ = occupancy_from_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    assert occ[12] == "."  # e2
    assert occ[28] == "W"  # e4


def test_bad_fen_raises():
    with pytest.raises(ValueError):
        occupancy_from_fen("not a fen")
