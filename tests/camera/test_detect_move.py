"""Test cases from contracts/interfaces.md section 2.6."""

import pytest

from checkmate.camera import START_FEN, detect_move

CASES = [
    ("normal",
     START_FEN,
     "WWWWWWWWWWWW.WWW............W...................BBBBBBBBBBBBBBBB",
     {"ok": True, "status": "move", "move": "e2e4"}),
    ("capture",
     "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
     "WWWWWWWWWWWW.WWW...................W............BBB.BBBBBBBBBBBB",
     {"ok": True, "status": "move", "move": "e4d5"}),
    ("castling",
     "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
     "WWWW.WW.WWWW.WWW.....W....W.W.....B.B.....B.....BBBB.BBBB.BBB.BB",
     {"ok": True, "status": "move", "move": "e1g1"}),
    ("en_passant",
     "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3",
     "WWWWWWWWWWWW.WWW...................B.........W..BBB.B.BBBBBBBBBB",
     {"ok": True, "status": "move", "move": "e5f6"}),
    ("promotion",
     "8/4P1k1/8/8/8/8/6K1/8 w - - 0 1",
     "..............W.......................................B.....W...",
     {"ok": True, "status": "promotion", "from": "e7", "to": "e8",
      "candidates": ["e7e8q", "e7e8r", "e7e8b", "e7e8n"]}),
    ("no_change",
     START_FEN,
     "WWWWWWWWWWWWWWWW................................BBBBBBBBBBBBBBBB",
     {"ok": True, "status": "no_change"}),
    ("invalid",
     START_FEN,
     "WWWWWWWWWWWW.WWW....................W...........BBBBBBBBBBBBBBBB",
     {"ok": True, "status": "invalid", "changed_squares": ["e2", "e5"]}),
]


@pytest.mark.parametrize("name,fen,occupancy,expected", CASES, ids=[c[0] for c in CASES])
def test_contract_cases(name, fen, occupancy, expected):
    assert detect_move(fen, occupancy) == expected


def test_capture_promotion():
    # White pawn on e7 takes the rook on d8.
    fen = "3r2k1/4P3/8/8/8/8/6K1/8 w - - 0 1"
    occ = list("." * 64)
    occ[14] = "W"  # g2 king
    occ[62] = "B"  # g8 king
    occ[59] = "W"  # d8 promoted piece
    r = detect_move(fen, "".join(occ))
    assert r["status"] == "promotion"
    assert r["candidates"] == ["e7d8q", "e7d8r", "e7d8b", "e7d8n"]


@pytest.mark.parametrize("fen,occupancy", [
    ("garbage", "W" * 64),
    (None, "W" * 64),
    (START_FEN, "W" * 63),
    (START_FEN, "w" * 64),
    (START_FEN, None),
])
def test_bad_request(fen, occupancy):
    r = detect_move(fen, occupancy)
    assert r["ok"] is False and r["error"] == "BAD_REQUEST"
