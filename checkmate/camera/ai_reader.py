"""Read the board with a vision model (DeepSeek), for camera.classifier "ai" (section 2.8).

The model only replaces the per-square color classification: it gets one picture, the
straightened board with a grid and each square's name written in it, and answers what stands on
each square. Everything else stays as it is: OpenCV finds the board, tells which side is white
and when the board is still, and the game loop works out the move.
"""

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor

import chess
import cv2
import numpy as np

from checkmate.camera.motion import MOTION_THRESHOLD, max_square_diff
from checkmate.camera.occupancy import occupancy_from_fen
from checkmate.config import REPO_ROOT
from checkmate.errors import err

API_KEY_ENV = "DEEPSEEK_API_KEY"
ENV_FILE = REPO_ROOT / ".env"  # git-ignored; the environment variable wins if both are set

# The picture: 80 px squares and half a square of the frame around the board, so pieces that
# lean outward near the edges are seen whole.
AI_CELL = 80
AI_MARGIN = AI_CELL // 2
AI_SIZE = 8 * AI_CELL + 2 * AI_MARGIN
GRID = (255, 200, 0)
# The edge of each square (this fraction of it) is grayed out: a tall piece leans away from the
# middle of the board, and its top in the next square's corner was read as a piece there.
EDGE = 0.2

SQUARES = [chess.square_name(i) for i in range(64)]  # a1, b1, ..., h8: the occupancy order (1.2)

# Only shows the answer format; the board in it is not the one in the picture.
_EXAMPLE = dict(obstructed=False, **dict(zip(SQUARES, occupancy_from_fen(
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"))))

PROMPT = f"""You read a chessboard for a chess robot. The picture is taken from straight above and
straightened: the board is a square with a grid drawn on it, and every square has its name
(a1 to h8) in a small black label in its top-left corner. The edge of every square is grayed
out: judge each square by its clear middle.

For every square, say what stands on it:
  "W"  a white (light-colored) piece
  "B"  a black (dark-colored) piece
  "."  nothing
Rules:
- A piece belongs to the square its base stands on. Tall pieces near the edges lean outward in
  the picture, so their tops can cover a neighboring square or the frame.
- Shadows, reflections, the colors of the squares and the labels are not pieces.
- "obstructed" is true if a hand, an arm or another object hides part of the board, else false.

Answer in json only, with "obstructed" and all 64 squares. This example shows the format, not
the board in the picture:
{json.dumps(_EXAMPLE, separators=(",", ":"))}"""

# What the model may write for a square, lowercased -> the occupancy character.
VALUES = {"w": "W", "white": "W", "b": "B", "black": "B", ".": ".", "": ".", "-": ".", "empty": "."}


def annotate(frame, corners_px) -> bytes:
    """The straightened board as JPEG: the frame around it, each square's edge grayed out, a
    grid, and each square's name.

    corners_px: the board corners a1, h1, h8, a8 in `frame`, as the calibration saved them.
    """
    lo, hi = AI_MARGIN, AI_MARGIN + 8 * AI_CELL
    target = np.float32([[lo, hi], [hi, hi], [hi, lo], [lo, lo]])  # a1 bottom left, a8 top left
    matrix = cv2.getPerspectiveTransform(np.float32(corners_px), target)
    img = cv2.warpPerspective(frame, matrix, (AI_SIZE, AI_SIZE))
    edges = np.ones(img.shape[:2], bool)
    ring = int(AI_CELL * EDGE)
    for x0 in range(lo, hi, AI_CELL):
        for y0 in range(lo, hi, AI_CELL):
            edges[y0 + ring:y0 + AI_CELL - ring, x0 + ring:x0 + AI_CELL - ring] = False
    img[edges] = (img[edges] * 0.25 + 96).astype(np.uint8)  # a quarter of the picture, on gray
    for k in range(9):
        p = lo + k * AI_CELL
        cv2.line(img, (p, lo), (p, hi), GRID, 1)
        cv2.line(img, (lo, p), (hi, p), GRID, 1)
    for square in chess.SQUARES:
        x = lo + chess.square_file(square) * AI_CELL
        y = lo + (7 - chess.square_rank(square)) * AI_CELL
        cv2.rectangle(img, (x + 2, y + 2), (x + 24, y + 16), (0, 0, 0), -1)
        cv2.putText(img, chess.square_name(square), (x + 4, y + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


def _names(squares, limit=8):
    return ", ".join(squares[:limit]) + (", ..." if len(squares) > limit else "")


def parse_answer(text):
    """The model's answer -> ({"occupancy", "obstructed"}, None), or (None, what was wrong).

    JSON mode only promises valid JSON (or blank content), not this format, so it is checked here.
    """
    if not text or not text.strip():
        return None, "it was empty"
    try:
        data = json.loads(text)
    except ValueError:
        return None, "it was not JSON"
    if not isinstance(data, dict):
        return None, "it was not a JSON object"
    data = {str(key).strip().lower(): value for key, value in data.items()}
    missing = [s for s in SQUARES if s not in data]
    unreadable = [s for s in SQUARES if s in data and
                  (not isinstance(data[s], str) or data[s].strip().lower() not in VALUES)]
    if missing or unreadable:
        wrong = ([f"missing {_names(missing)}"] if missing else []) + \
                ([f"unreadable {_names(unreadable)}"] if unreadable else [])
        return None, "; ".join(wrong)
    obstructed = data.get("obstructed", False)
    if isinstance(obstructed, str):
        obstructed = obstructed.strip().lower() == "true"
    occupancy = "".join(VALUES[data[s].strip().lower()] for s in SQUARES)
    return {"occupancy": occupancy, "obstructed": bool(obstructed)}, None


class DeepSeekReader:
    """One picture in, the 64 squares out, from DeepSeek's vision model (OpenAI-compatible API).

    read() never raises (section 0.2): a network or service problem is AI_UNAVAILABLE, and an
    answer that is still unusable after the retries is AI_BAD_ANSWER.
    """

    def __init__(self, config: dict, client=None):
        self.model = config.get("model", "deepseek-flash")
        self.base_url = config.get("base_url", "https://api.deepseek.com")
        self.thinking = bool(config.get("thinking", False))
        self.temperature = float(config.get("temperature", 0.0))
        # A retry at temperature 0 would most likely repeat the same answer.
        self.retry_temperature = float(config.get("retry_temperature", 0.5))
        self.retries = int(config.get("retries", 2))
        self.timeout_s = float(config.get("timeout_s", 15.0))
        self.max_tokens = int(config.get("max_tokens", 2000))
        self._client = client  # tests pass a fake

    def _connect(self):
        if self._client is None:
            key = os.environ.get(API_KEY_ENV)
            if not key and ENV_FILE.exists():
                from dotenv import dotenv_values  # python-dotenv
                key = dotenv_values(ENV_FILE).get(API_KEY_ENV)
            if not key:
                raise RuntimeError(f"{API_KEY_ENV} is not set (in the environment or in {ENV_FILE.name})")
            from openai import OpenAI  # only needed with classifier "ai"
            self._client = OpenAI(api_key=key, base_url=self.base_url, timeout=self.timeout_s,
                                  max_retries=0)
        return self._client

    def read(self, jpeg: bytes) -> dict:
        """{"ok": True, "occupancy": 64 chars, "obstructed": bool}, or an error."""
        try:
            client = self._connect()
        except Exception as e:
            return err("AI_UNAVAILABLE", str(e))
        image = {"type": "image_url",
                 "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}}
        problem = None
        for attempt in range(1 + self.retries):
            ask = "Read every square." if problem is None else \
                f"Your last answer was unusable ({problem}). Read every square again."
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": PROMPT},
                              {"role": "user", "content": [image, {"type": "text", "text": ask}]}],
                    response_format={"type": "json_object"},
                    temperature=self.temperature if attempt == 0 else self.retry_temperature,
                    max_tokens=self.max_tokens,
                    extra_body={"thinking": {"type": "enabled" if self.thinking else "disabled"}},
                )
            except Exception as e:
                return err("AI_UNAVAILABLE", f"{type(e).__name__}: {e}")
            choice = response.choices[0]
            if choice.finish_reason == "length":
                problem = "it was cut off"
                continue
            result, problem = parse_answer(choice.message.content)
            if result is not None:
                return {"ok": True, **result}
        return err("AI_BAD_ANSWER", f"no usable answer in {1 + self.retries} tries: {problem}")


class AiClassifier:
    """Asks `reader` to read the board each time it settles in a new state.

    The camera thread feeds it every analyzed frame. A read is asked for when the board is still
    and differs from the last board read; it runs in a worker thread, and its answer is dropped if
    anything moved meanwhile. Until the board as it is now has been read, the observation is not
    stable, so the game loop waits, as it does while a hand is over the board.
    """

    def __init__(self, reader, retry_s=2.0, give_up_s=15.0, pool=None):
        self.reader = reader
        self.retry_s = retry_s        # after a failed read
        self.give_up_s = give_up_s    # reads failing this long: problem() says so
        self._pool = pool             # tests pass their own; otherwise made on the first read
        self.reset()

    def reset(self):
        """Forget everything read, e.g. after calibrating."""
        self.occupancy = None         # the last good read
        self.last_error = None
        self.last_picture = None      # JPEG of the last read asked for, for /api/ai.jpg
        self._ref = None              # the board (motion.shrink) of that read
        self._epoch = 0               # one more for every frame with motion
        self._read_epoch = None       # the still period the last good read belongs to
        self._blocked_epoch = None    # still period with a hand in the picture: wait for motion
        self._pending = None          # (future, epoch, board) of the read in flight
        self._retry_at = 0.0
        self._failing_since = None

    def close(self):
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None
        self._pending = None

    def update(self, frame, corners_px, board, stable, now):
        """Feed one analyzed frame; `board` is motion.shrink() of it.

        Returns (occupancy, current): the last board read (None before the first read), and
        whether that read is of the board as it is now.
        """
        if not stable:
            self._epoch += 1
        self._collect(now)
        if not stable:
            return self.occupancy, False
        if self._read_epoch == self._epoch:
            return self.occupancy, True
        if self._pending is not None or self._blocked_epoch == self._epoch or now < self._retry_at:
            return self.occupancy, False
        if self._ref is not None and max_square_diff(board, self._ref) <= MOTION_THRESHOLD:
            self._read_epoch = self._epoch  # a hand came and went, nothing on the board changed
            return self.occupancy, True
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="camera-ai")
        self._pending = (self._pool.submit(self._read, frame.copy(), corners_px), self._epoch, board)
        return self.occupancy, False

    def problem(self, now):
        """Why the board can't be read, once reads have failed for give_up_s, else None."""
        if self._failing_since is not None and now - self._failing_since >= self.give_up_s:
            return f"can't read the board with the AI: {self.last_error}"
        return None

    def _read(self, frame, corners_px):
        try:
            self.last_picture = annotate(frame, corners_px)
            return self.reader.read(self.last_picture)
        except Exception as e:
            return err("AI_UNAVAILABLE", f"{type(e).__name__}: {e}")

    def _collect(self, now):
        """Take the answer of the read in flight, if it is done."""
        if self._pending is None or not self._pending[0].done():
            return
        future, epoch, board = self._pending
        self._pending = None
        res = future.result()
        if not res["ok"]:
            self.last_error = res["message"]
            if self._failing_since is None:
                self._failing_since = now
            self._retry_at = now + self.retry_s
            return
        self._failing_since = self.last_error = None
        if epoch != self._epoch:
            return  # something moved while it was read: read again once it is still
        if res["obstructed"]:
            self._blocked_epoch = epoch
            return
        self.occupancy, self._ref, self._read_epoch = res["occupancy"], board, epoch
