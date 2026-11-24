"""The vision-model reader (camera.classifier "ai"), with a fake DeepSeek client: no network."""

import json
import sys
from concurrent.futures import Future
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from checkmate.camera import ai_reader, occupancy_from_fen
from checkmate.camera.ai_reader import (AI_CELL, AI_MARGIN, AI_SIZE, PROMPT, SQUARES, AiClassifier,
                                        DeepSeekReader, annotate, parse_answer)
from tests.camera.synthetic import AFTER_E4, START_OCC, expected_corners, render


def answer(occupancy, obstructed=False):
    return json.dumps(dict(obstructed=obstructed, **dict(zip(SQUARES, occupancy))))


# -- the picture --------------------------------------------------------------------------------

def _square_center(img, name):
    file, rank = "abcdefgh".index(name[0]), int(name[1]) - 1
    x = AI_MARGIN + file * AI_CELL + AI_CELL // 2
    y = AI_MARGIN + (7 - rank) * AI_CELL + AI_CELL // 2
    return img[y - 10:y + 10, x - 10:x + 10].mean()


def test_annotate_straightens_the_board_with_a1_bottom_left():
    img = cv2.imdecode(np.frombuffer(annotate(render(START_OCC), expected_corners()), np.uint8),
                       cv2.IMREAD_GRAYSCALE)
    assert img.shape == (AI_SIZE, AI_SIZE)
    # synthetic.py draws white pieces as light discs and black ones as dark discs
    assert _square_center(img, "a1") > 200 and _square_center(img, "e2") > 200
    assert _square_center(img, "a8") < 60 and _square_center(img, "h7") < 60
    # the edge of each square is grayed out, its middle isn't (e4 is an empty light square)
    x0, y0 = AI_MARGIN + 4 * AI_CELL, AI_MARGIN + 4 * AI_CELL
    middle = img[y0 + 30:y0 + 50, x0 + 30:x0 + 50].mean()
    edge = img[y0 + 30:y0 + 50, x0 + 4:x0 + 12].mean()
    assert middle > 200 and 100 < edge < 160
    # a label in each square's top-left corner
    label = img[AI_MARGIN + 7 * AI_CELL + 4:AI_MARGIN + 7 * AI_CELL + 14, AI_MARGIN + 4:AI_MARGIN + 22]
    assert (label < 60).mean() > 0.5 and (label > 200).any()  # black box, white letters (a1)


def test_prompt_asks_for_json_with_an_example():
    # DeepSeek's JSON mode needs the word "json" and an example of the format
    assert "json" in PROMPT and '"obstructed":false' in PROMPT and '"h8":"B"' in PROMPT


# -- checking the answer ------------------------------------------------------------------------

def test_parse_a_good_answer():
    assert parse_answer(answer(START_OCC)) == ({"occupancy": START_OCC, "obstructed": False}, None)
    assert parse_answer(answer(START_OCC, obstructed=True))[0]["obstructed"] is True


def test_parse_accepts_other_spellings():
    data = dict(zip(SQUARES, START_OCC))
    data.update({"a1": "w", "e8": "black", "e4": "empty", "E5": " . "})
    data["obstructed"] = "false"
    result, problem = parse_answer(json.dumps(data))
    assert problem is None and result == {"occupancy": START_OCC, "obstructed": False}


@pytest.mark.parametrize("text, problem", [
    ("", "it was empty"),
    ("   ", "it was empty"),            # JSON mode replaces non-JSON output with spaces
    ("a1 is white", "it was not JSON"),
    ("[1, 2]", "it was not a JSON object"),
])
def test_parse_rejects_what_is_not_an_answer(text, problem):
    assert parse_answer(text) == (None, problem)


def test_parse_names_missing_and_unreadable_squares():
    data = dict(zip(SQUARES, START_OCC))
    del data["c4"], data["e5"]
    data["a1"], data["b1"] = "rook", None
    result, problem = parse_answer(json.dumps(data))
    assert result is None
    assert problem == "missing c4, e5; unreadable a1, b1"


# -- the DeepSeek request -----------------------------------------------------------------------

class FakeClient:
    """Stands in for openai.OpenAI: answers with `replies` (text, or an exception to raise)."""

    def __init__(self, *replies, finish_reason="stop"):
        self.replies = list(replies)
        self.finish_reason = finish_reason
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        message = SimpleNamespace(content=reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)])


def test_request_sends_the_picture_in_json_mode_without_thinking():
    client = FakeClient(answer(START_OCC))
    assert DeepSeekReader({}, client=client).read(b"jpeg bytes") == \
        {"ok": True, "occupancy": START_OCC, "obstructed": False}
    req = client.requests[0]
    assert req["model"] == "deepseek-flash"
    assert req["response_format"] == {"type": "json_object"}
    assert req["temperature"] == 0
    assert req["extra_body"] == {"thinking": {"type": "disabled"}}
    system, user = req["messages"]
    assert system == {"role": "system", "content": PROMPT}
    image = user["content"][0]
    assert image["type"] == "image_url"
    assert image["image_url"]["url"] == "data:image/jpeg;base64,anBlZyBieXRlcw=="


def test_unusable_answer_is_asked_again_warmer_and_with_what_was_wrong():
    client = FakeClient("", answer(START_OCC))
    assert DeepSeekReader({}, client=client).read(b"x")["occupancy"] == START_OCC
    retry = client.requests[1]
    assert retry["temperature"] == 0.5
    assert "it was empty" in retry["messages"][1]["content"][1]["text"]


def test_answers_cut_off_are_retried_then_given_up():
    client = FakeClient("{", "{", "{", finish_reason="length")
    res = DeepSeekReader({"retries": 2}, client=client).read(b"x")
    assert res["error"] == "AI_BAD_ANSWER" and "cut off" in res["message"]
    assert len(client.requests) == 3


def test_network_error_is_returned_not_raised():
    res = DeepSeekReader({}, client=FakeClient(ConnectionError("no route"))).read(b"x")
    assert res["error"] == "AI_UNAVAILABLE" and "no route" in res["message"]


def test_missing_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(ai_reader, "ENV_FILE", tmp_path / ".env")  # no .env either
    res = DeepSeekReader({}).read(b"x")
    assert res == {"ok": False, "error": "AI_UNAVAILABLE",
                   "message": "DEEPSEEK_API_KEY is not set (in the environment or in .env)"}


def test_api_key_from_the_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# DeepSeek\nDEEPSEEK_API_KEY=sk-from-file\n")
    monkeypatch.setattr(ai_reader, "ENV_FILE", env_file)
    made = []
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kw: made.append(kw) or "client"))

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    DeepSeekReader({})._connect()
    assert made[-1]["api_key"] == "sk-from-file" and made[-1]["base_url"] == "https://api.deepseek.com"

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-environment")  # the environment wins
    DeepSeekReader({})._connect()
    assert made[-1]["api_key"] == "sk-from-environment"


# -- when to read -------------------------------------------------------------------------------

class HandPool:
    """A worker pool the test finishes by hand: finish() runs the oldest read."""

    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args):
        future = Future()
        self.jobs.append((future, fn, args))
        return future

    def finish(self):
        future, fn, args = self.jobs.pop(0)
        future.set_result(fn(*args))

    def shutdown(self, **kwargs):
        pass


class ScriptedReader:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    def read(self, jpeg):
        self.calls += 1
        return self.results.pop(0)


def ok(occupancy, obstructed=False):
    return {"ok": True, "occupancy": occupancy, "obstructed": obstructed}


START_BOARD = np.zeros((64, 64), np.float32)
CHANGED_BOARD = START_BOARD.copy()
CHANGED_BOARD[48:56, 32:40] = 255   # e2 looks different


def make(*results, **kwargs):
    reader, pool = ScriptedReader(*results), HandPool()
    return AiClassifier(reader, pool=pool, **kwargs), reader, pool


def feed(ai, board=START_BOARD, stable=True, now=0.0):
    return ai.update(render(START_OCC), expected_corners(), board, stable, now)


def test_reads_once_the_board_is_still_and_reports_it_then():
    ai, reader, pool = make(ok(START_OCC))
    assert feed(ai, stable=False) == (None, False)
    assert not pool.jobs                         # nothing is read while something moves
    assert feed(ai) == (None, False)             # still: a read is asked for
    assert len(pool.jobs) == 1
    assert feed(ai) == (None, False)             # no second read while one is in flight
    pool.finish()
    assert feed(ai) == (START_OCC, True)
    assert feed(ai) == (START_OCC, True) and reader.calls == 1


def test_nothing_changed_on_the_board_no_new_read():
    ai, reader, pool = make(ok(START_OCC))
    feed(ai)
    pool.finish()
    feed(ai)
    feed(ai, stable=False)                       # a hand came and went
    assert feed(ai) == (START_OCC, True)
    assert not pool.jobs and reader.calls == 1


def test_a_changed_board_is_read_again():
    after = occupancy_from_fen(AFTER_E4)
    ai, reader, pool = make(ok(START_OCC), ok(after))
    feed(ai)
    pool.finish()
    feed(ai)
    feed(ai, CHANGED_BOARD, stable=False)
    assert feed(ai, CHANGED_BOARD) == (START_OCC, False)   # the old read isn't the board now
    pool.finish()
    assert feed(ai, CHANGED_BOARD) == (after, True)


def test_answer_is_dropped_if_the_board_moved_while_it_was_read():
    after = occupancy_from_fen(AFTER_E4)
    ai, reader, pool = make(ok("." * 64), ok(after))
    feed(ai)                                      # read 1 starts
    feed(ai, CHANGED_BOARD, stable=False)         # ... and the hand comes back
    pool.finish()
    assert feed(ai, CHANGED_BOARD) == (None, False)  # read 1 is dropped, read 2 starts
    assert len(pool.jobs) == 1
    pool.finish()
    assert feed(ai, CHANGED_BOARD) == (after, True)


def test_a_hand_in_the_picture_waits_for_motion():
    ai, reader, pool = make(ok(START_OCC, obstructed=True), ok(START_OCC))
    feed(ai)
    pool.finish()
    assert feed(ai) == (None, False)
    assert feed(ai) == (None, False) and not pool.jobs   # the same still picture isn't sent again
    feed(ai, stable=False)                               # the hand moves away
    feed(ai)
    pool.finish()
    assert feed(ai) == (START_OCC, True)


def test_failed_reads_are_retried_and_reported_after_a_while():
    down = {"ok": False, "error": "AI_UNAVAILABLE", "message": "no route"}
    ai, reader, pool = make(down, down, ok(START_OCC), retry_s=2.0, give_up_s=5.0)
    feed(ai, now=0)                                             # read 1
    pool.finish()                                               # ... fails
    assert feed(ai, now=1) == (None, False) and not pool.jobs   # seen at 1: next try at 3
    assert ai.problem(1) is None
    feed(ai, now=3.5)                                           # read 2
    pool.finish()                                               # ... fails
    feed(ai, now=4)                                             # seen at 4: next try at 6
    assert ai.problem(6.5) == "can't read the board with the AI: no route"  # failing since 1
    feed(ai, now=6)                                             # read 3
    pool.finish()                                               # ... works
    assert feed(ai, now=7) == (START_OCC, True)
    assert ai.problem(7) is None
