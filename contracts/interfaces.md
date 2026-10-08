# CheckMate Interface Contracts (v1)

This file defines **what each module takes in, what it gives back, and how it behaves when something goes wrong**, so that everyone can build and test their part alone and plug it together later.

If you need to change anything here (a field name, a function, a message), tell the people whose module uses it **before** you change your code, then update this file.

---

## 0. Overview

### 0.1 Who owns what

| Module | Owner | Runs on | Language | Delivers |
|---|---|---|---|---|
| Camera + move detection | Harry | Raspberry Pi | Python 3 + OpenCV | `checkmate/camera.py`: class `Camera`, functions `detect_move`, `occupancy_from_fen` |
| Engine / game state | Joel | Raspberry Pi | Python 3 + python-chess + Stockfish | `checkmate/engine.py`: class `GameEngine` |
| LED (Pi side) | Hsin-Chen | Raspberry Pi | Python 3 + pyserial | `checkmate/led.py`: class `LedController` |
| LED (firmware) | Hsin-Chen | Pico | MicroPython | `pico/main.py` |
| UI | Jayden | Chromium (kiosk) on the touchscreen | HTML/JS or TS (any frontend framework) | built static files in `ui/dist/`, talking to the backend over the API in section 5 |
| Backend server + main loop | everyone | Raspberry Pi | Python 3 + **FastAPI** + uvicorn | `checkmate/server.py` (FastAPI app), `checkmate/main.py` (game loop) |

### 0.2 How the pieces connect

```
                    UI (Jayden): web page in Chromium kiosk
                         ▲
                         │ HTTP + WebSocket, http://127.0.0.1:8000  (section 5)
                         ▼
                         ┌──────────────────────────────┐
                         │  server.py (FastAPI/uvicorn) │
                         │  main.py (game loop thread)  │
                         │  holds phase, calls modules  │
                         └──┬──────────┬──────────┬─────┘
             function calls │          │          │ function calls
            ┌───────────────┘          │          └───────────────┐
            ▼                          ▼                          ▼
   Camera (Harry)              GameEngine (Joel)          LedController (Hsin-Chen)
   OpenCV, Picamera2           python-chess +                    │ USB serial, JSON lines
                               /usr/games/stockfish              ▼
                                                           Pico firmware → 8×8 LEDs
```

Rules:
1. **Modules never call each other.** Only `main.py` calls them and passes data between them. For example, the camera never asks the engine for the FEN; main passes the FEN in.
2. **Everything that crosses a boundary is a plain `dict` / `list` / `str` / `int` / `float` / `bool` / `None`**, so it is JSON-serializable. No custom classes, no `chess.Board`, no numpy arrays.
3. **Module functions do not raise exceptions to main.** They return `{"ok": false, "error": CODE, "message": "..."}` instead (section 1.5). The only exception is `__init__`, which may raise if the config is invalid.
4. The engine module holds the **only** game state (`chess.Board`). The camera, LED and UI never keep their own copy of the position.

### 0.3 Lifecycle (same for every Python module)

```python
cam = Camera(config["camera"])          # must not touch hardware yet
cam.start()  -> {"ok": True} | error    # open camera / start Stockfish / open serial port
...
cam.close()  -> None                    # release hardware; safe to call twice
```
`GameEngine`, `LedController` follow the same `__init__(config) / start() / close()` pattern.

---

## 1. Shared conventions

### 1.1 Basic formats

| Thing | Format | Example |
|---|---|---|
| Square | lowercase algebraic, `^[a-h][1-8]$` | `"e4"` |
| Move | UCI, lowercase | normal `"e2e4"`, capture `"e4d5"`, castling `"e1g1"` / `"e1c1"` / `"e8g8"` / `"e8c8"`, promotion `"e7e8q"` (`q r b n`) |
| SAN | standard notation, for display only | `"Nf3"`, `"exd5"`, `"O-O"`, `"e8=Q+"` |
| Position | full FEN (6 fields) | `"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"` |
| Color | `"white"` / `"black"` | |
| Occupancy | 64-char string, see 1.2 | |
| Timestamp | `float` seconds from `time.monotonic()` | `1532.41` |
| Elo | `int`, 1320–3190 | `1500` |

`START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"`

### 1.2 Occupancy string

The camera can see **whether a square has a piece and whether it's white or black**, but not which piece it is. So the board is a 64-character string:

- character `i` is square `i` in python-chess order: **a1, b1, …, h1, a2, …, h8** (`chess.square_name(i)`; a1 = 0, h1 = 7, a2 = 8, a8 = 56, h8 = 63)
- `W` = white piece, `B` = black piece, `.` = empty
- always exactly 64 chars, uppercase, nothing else

Starting position:
```
WWWWWWWWWWWWWWWW................................BBBBBBBBBBBBBBBB
└── a1 … h1 ──┘└── a2 … h2 ──┘                  └ a7 … h7 ┘└ a8 … h8 ┘
```
Square `e2` is index `4 + 8*1 = 12`, square `e4` is index `4 + 8*3 = 28`. In general `index = file + 8 * (rank - 1)`, with file a=0 … h=7.

### 1.3 Moves on the physical board

| Move type | Squares that change in occupancy | Example (UCI) |
|---|---|---|
| Normal | 2: from → empty, to → mover's color | `e2e4` |
| Capture | 2: from → empty, to changes from opponent's color to mover's | `e4d5` |
| Castling | 4: king from/to and rook from/to | `e1g1` (rook `h1→f1`), `e1c1` (rook `a1→d1`), `e8g8` (rook `h8→f8`), `e8c8` (rook `a8→d8`) |
| En passant | 3: from → empty, to → mover's, captured pawn's square → empty | `e5f6` removes the pawn on `f5` |
| Promotion | 2 (same as normal or capture), but the pawn is swapped for a new piece | `e7e8q` |

### 1.4 Shared helper: `occupancy_from_fen(fen: str) -> str` (owner: Harry)

Converts a FEN to the occupancy string the camera should see. Everyone uses this in tests and fakes.
```python
occupancy_from_fen(START_FEN)
# "WWWWWWWWWWWWWWWW................................BBBBBBBBBBBBBBBB"
```

### 1.5 Errors

Every function returns either its normal result (which includes `"ok": true`) or:
```json
{ "ok": false, "error": "ILLEGAL_MOVE", "message": "e2e5 is not legal in this position" }
```
`message` is for humans and logs; code must only check `error`.

| Code | Returned by | Meaning |
|---|---|---|
| `BAD_REQUEST` | any | wrong argument type or format (e.g. square `"z9"`, occupancy of length 63) |
| `NOT_ALLOWED` | server | UI command not allowed in the current phase (5.4) |
| `NOT_STARTED` | any | `start()` was not called or failed |
| `CAMERA_NOT_READY` | camera | no frames, or not calibrated yet |
| `CALIBRATION_FAILED` | camera | couldn't find the board corners |
| `ILLEGAL_MOVE` | engine | move is not legal in the current position |
| `GAME_OVER` | engine | game has ended; no more moves accepted |
| `NO_GAME` | engine | `new_game` hasn't been called |
| `ENGINE_ERROR` | engine | Stockfish crashed, didn't start, or timed out |
| `LED_DISCONNECTED` | led | Pico not connected or not answering |
| `LED_REJECTED` | led | Pico answered with an error |

### 1.6 Config file: `config.json`

One file, one section per module. Each module only reads its own section.
```json
{
  "camera": {
    "backend": "picamera2",
    "device_index": 0,
    "width": 1280,
    "height": 720,
    "calibration_file": "calibration.json",
    "stable_time_s": 0.5
  },
  "engine": {
    "stockfish_path": "/usr/games/stockfish",
    "threads": 2,
    "hash_mb": 64,
    "think_time_s": 1.0
  },
  "led": {
    "port": "/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_*-if00",
    "reply_timeout_s": 0.5,
    "brightness": 40
  },
  "server": {
    "host": "127.0.0.1",
    "port": 8000,
    "static_dir": "ui/dist"
  }
}
```
`camera.backend`: `"picamera2"` for the Raspberry Pi camera module, `"v4l2"` for a USB webcam.

---

## 2. Camera: Harry

The camera module turns frames into an occupancy string. It does **not** know chess rules, except inside `detect_move`, which uses python-chess only to list legal moves.

### 2.1 `Camera.start() -> dict`
Opens the camera and starts a background thread that reads frames continuously, so `get_observation()` returns immediately. Loads `calibration_file` if it exists.

| Result | When |
|---|---|
| `{"ok": true, "calibrated": true}` | camera open, calibration loaded |
| `{"ok": true, "calibrated": false}` | camera open, no calibration file yet; main must call `calibrate()` |
| `{"ok": false, "error": "CAMERA_NOT_READY", ...}` | camera couldn't be opened |

### 2.2 `Camera.calibrate() -> dict`
Finds the board in the current frame (e.g. 4 ArUco markers on the board corners, or a fixed manual corner list), computes the perspective warp to a top-down 8×8 grid, works out which corner is a1, and saves everything to `calibration_file`. Takes ≤ 5 s. **The board should be in the starting position** while calibrating, so the module can check orientation: white pieces must be on ranks 1–2.

Output:
```json
{
  "ok": true,
  "corners_px": [[102, 88], [1180, 95], [1175, 690], [98, 684]],
  "frame_size": [1280, 720],
  "occupancy": "WWWWWWWWWWWWWWWW................................BBBBBBBBBBBBBBBB"
}
```
| Field | Type | Meaning |
|---|---|---|
| `corners_px` | `[[x,y] ×4]` | outer board corners in the raw frame, order: **a1 corner, h1 corner, h8 corner, a8 corner** |
| `frame_size` | `[w, h]` | resolution the calibration was made at |
| `occupancy` | str | what the camera sees right after calibrating, so main/UI can check it |

Errors: `CAMERA_NOT_READY`, `CALIBRATION_FAILED`.

### 2.3 `Camera.get_observation() -> dict`
Returns the latest processed board. Must return in **< 50 ms** (it just reads the result of the background thread).

```json
{
  "ok": true,
  "ts": 1532.41,
  "seq": 1841,
  "stable": true,
  "occupancy": "WWWWWWWWWWWW.WWW............W...................BBBBBBBBBBBBBBBB",
  "low_confidence": ["d5"]
}
```
| Field | Type | Meaning |
|---|---|---|
| `ts` | float | `time.monotonic()` when the frame was taken |
| `seq` | int | frame counter, increases by 1 per processed frame |
| `stable` | bool | `true` only if nothing in the board area has moved for `stable_time_s` (default 0.5 s), i.e. no hand over the board. **Main only uses stable observations.** |
| `occupancy` | str | 64-char string (1.2). When `stable` is `false`, this is the last frame's best guess and must not be trusted. |
| `low_confidence` | list of squares | squares where the classifier isn't sure. Can be empty. |

Errors: `CAMERA_NOT_READY` (not started or not calibrated).

### 2.4 `Camera.get_debug_image() -> bytes | None` (optional, nice to have)
JPEG of the warped top-down board with the grid and detected colors drawn on. The UI can show it on a "camera check" screen. `None` if there's no frame.

### 2.5 `detect_move(fen: str, occupancy: str) -> dict` (pure function)
Works out what move was made, given the **position before the move** and a **stable** occupancy after it. No camera or hardware access, so it can be unit-tested on a laptop.

How it should work: for every legal move in `fen`, compute the occupancy after that move (push it on a copy of the board, then `occupancy_from_fen`), and compare with the given occupancy.

| `status` | When | Other fields |
|---|---|---|
| `"move"` | exactly one legal move matches | `move`: UCI string |
| `"promotion"` | a pawn reached the last rank; all 4 promotion moves give the same occupancy | `candidates`: 4 UCI strings, `from`, `to` |
| `"no_change"` | occupancy equals `occupancy_from_fen(fen)` | none |
| `"invalid"` | no legal move matches | `changed_squares`: list of squares that differ from `occupancy_from_fen(fen)` |

```json
{ "ok": true, "status": "move", "move": "e2e4" }
{ "ok": true, "status": "promotion", "from": "e7", "to": "e8", "candidates": ["e7e8q", "e7e8r", "e7e8b", "e7e8n"] }
{ "ok": true, "status": "no_change" }
{ "ok": true, "status": "invalid", "changed_squares": ["e2", "e5"] }
```
Errors: `BAD_REQUEST` (bad FEN, or occupancy not 64 chars of `W B .`).

Main uses it in two places:
- **Human's move:** `detect_move(engine.state()["fen"], obs["occupancy"])`
- **Checking the human played the engine's move:** same call; it's correct if `status == "move"` and `move == engine_move["move"]`, or (engine promotion) `status == "promotion"` and `engine_move["move"] in candidates`.

### 2.6 Test cases for `detect_move` (all generated and checked with python-chess 1.11.2)

| Case | `fen` (before) | `occupancy` (after) | Expected |
|---|---|---|---|
| Normal | `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1` | `WWWWWWWWWWWW.WWW............W...................BBBBBBBBBBBBBBBB` | `move`, `e2e4` |
| Capture | `rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2` | `WWWWWWWWWWWW.WWW...................W............BBB.BBBBBBBBBBBB` | `move`, `e4d5` |
| Castling | `r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4` | `WWWW.WW.WWWW.WWW.....W....W.W.....B.B.....B.....BBBB.BBBB.BBB.BB` | `move`, `e1g1` |
| En passant | `rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3` | `WWWWWWWWWWWW.WWW...................B.........W..BBB.B.BBBBBBBBBB` | `move`, `e5f6` |
| Promotion | `8/4P1k1/8/8/8/8/6K1/8 w - - 0 1` | `..............W.......................................B.....W...` | `promotion`, `e7e8q/r/b/n` |
| No change | `START_FEN` | `WWWWWWWWWWWWWWWW................................BBBBBBBBBBBBBBBB` | `no_change` |
| Invalid (pawn put on e5) | `START_FEN` | `WWWWWWWWWWWW.WWW....................W...........BBBBBBBBBBBBBBBB` | `invalid`, `changed_squares: ["e2","e5"]` |

### 2.7 Fake camera (for teammates without hardware)
`FakeCamera` has the same methods. Tests set `fake.occupancy = "..."` and `fake.stable = True/False`, and `get_observation()` returns them. `calibrate()` always succeeds.

### 2.8 Technical notes (from official docs)
- Raspberry Pi OS uses libcamera. For the Pi camera module, capture with **Picamera2** (`picam2.capture_array()`); `cv2.VideoCapture(0)` usually does **not** work with it. USB webcams work with `cv2.VideoCapture(0, cv2.CAP_V4L2)`.
- In Picamera2, format `"RGB888"` gives pixels in **B, G, R** order, which is what OpenCV expects. The default preview format `XBGR8888` has 4 channels.
- `apt install python3-opencv` on Bookworm gives OpenCV 4.6 (old ArUco API, `cv2.aruco.detectMarkers`). `cv2.aruco.ArucoDetector` needs ≥ 4.7 (pip `opencv-python` in a venv created with `--system-site-packages`, so Picamera2 stays visible).
- Lock exposure and white balance after warm-up (`AeEnable`/`AwbEnable` = False), so the classification doesn't drift when lighting changes.

---

## 3. Engine / game state: Joel

`GameEngine` wraps one `chess.Board` (the **only** game state in the system) and a local Stockfish started with `chess.engine.SimpleEngine.popen_uci(config["stockfish_path"])`.

### 3.1 `GameEngine.start() -> dict`
Starts Stockfish and sets `Threads` and `Hash` from config.
```json
{ "ok": true, "engine_name": "Stockfish 17", "elo_min": 1320, "elo_max": 3190 }
```
`elo_min` / `elo_max` are read from `engine.options["UCI_Elo"]` (they depend on the Stockfish version: 1320–3190 from Stockfish 16 on). The UI uses them for the difficulty slider.
Errors: `ENGINE_ERROR` (binary not found or didn't start).

### 3.2 `GameEngine.new_game(human_color: str, elo: int, mode: str = "play") -> dict`

| Param | Type | Meaning |
|---|---|---|
| `human_color` | `"white"` / `"black"` | color the human plays |
| `elo` | int | engine strength; clamped to `[elo_min, elo_max]`. Sets `UCI_LimitStrength = true`, `UCI_Elo = elo`. |
| `mode` | `"play"` / `"practice"` | in `practice`, `rate_last_move()` is used after each human move |

Resets the board to `START_FEN`. Returns `state()`. Errors: `BAD_REQUEST`, `ENGINE_ERROR`.

Suggested difficulty presets for the UI:

| Label | Elo |
|---|---|
| Beginner | 1320 |
| Casual | 1500 |
| Club | 1800 |
| Strong | 2200 |
| Max | 3190 |

### 3.3 `GameEngine.state() -> dict`
Never fails once a game exists (otherwise `NO_GAME`). Cheap: no Stockfish call.
```json
{
  "ok": true,
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "turn": "black",
  "human_color": "white",
  "elo": 1500,
  "mode": "play",
  "fullmove_number": 1,
  "moves_uci": ["e2e4"],
  "moves_san": ["e4"],
  "last_move": "e2e4",
  "in_check": false,
  "check_square": null,
  "game_over": false,
  "result": null,
  "termination": null
}
```
| Field | Type | Meaning |
|---|---|---|
| `fen` | str | current position |
| `turn` | color | side to move |
| `moves_uci` / `moves_san` | list | full move history, same length |
| `last_move` | UCI or `null` | last move played |
| `in_check` | bool | side to move is in check |
| `check_square` | square or `null` | square of the king in check (for the `check` LED) |
| `game_over` | bool | from `board.outcome(claim_draw=True)` or resignation |
| `result` | `"1-0"` / `"0-1"` / `"1/2-1/2"` / `null` | |
| `termination` | str or `null` | `"CHECKMATE"`, `"STALEMATE"`, `"INSUFFICIENT_MATERIAL"`, `"THREEFOLD_REPETITION"`, `"FIFTY_MOVES"`, `"FIVEFOLD_REPETITION"`, `"SEVENTYFIVE_MOVES"`, `"RESIGNATION"` (python-chess `Termination` names, plus `RESIGNATION`) |

Use `claim_draw=True` so threefold and fifty-move draws end the game automatically; nobody can press "claim draw" on a physical board.

### 3.4 `GameEngine.push_move(uci: str) -> dict`
Applies a move to the board: the human's move, or the engine's move **after** the camera confirmed it was played.
```json
{ "ok": true, "san": "e4", "state": { "...": "same as state()" } }
{ "ok": false, "error": "ILLEGAL_MOVE", "message": "e2e5 is not legal" }
```
Errors: `BAD_REQUEST` (not UCI), `ILLEGAL_MOVE`, `GAME_OVER`, `NO_GAME`.

### 3.5 `GameEngine.get_engine_move() -> dict`
Asks Stockfish for its move in the current position, using `chess.engine.Limit(time=think_time_s)`. **Does not apply it.** Blocks for about `think_time_s` (≤ `think_time_s + 2` s worst case).
```json
{
  "ok": true,
  "move": "e1g1",
  "san": "O-O",
  "from": "e1",
  "to": "g1",
  "rook_from": "h1",
  "rook_to": "f1",
  "capture_square": null,
  "promotion": null
}
```
| Field | Type | Meaning |
|---|---|---|
| `move` | UCI | the move |
| `from` / `to` | square | where the moving piece starts and ends (for castling, the king) |
| `rook_from` / `rook_to` | square or `null` | only for castling |
| `capture_square` | square or `null` | square of the captured piece. Equals `to` for a normal capture; for en passant it's the pawn's actual square (e.g. `e5f6` → `"f5"`) |
| `promotion` | `"q"`/`"r"`/`"b"`/`"n"`/`null` | piece the pawn becomes; the human must swap the pawn for that piece |

Errors: `ENGINE_ERROR` (crash or timeout; main may call `start()` again and retry), `GAME_OVER`, `NO_GAME`.
Note: python-chess's built-in timeout only applies when `Limit.time` is set, so **always** set it.

### 3.6 `GameEngine.get_hint() -> dict`
Best move for the side to move (the human). Same fields as `get_engine_move()`. Blocks ≤ `think_time_s`. Uses full strength (not the limited Elo).

### 3.7 `GameEngine.rate_last_move() -> dict`
Rates the last move played. Used in `practice` mode after each human move. Scores are in centipawns from **White's point of view**.
```json
{
  "ok": true,
  "played": "f2f3",
  "played_san": "f3",
  "best": "g1f3",
  "best_san": "Nf3",
  "score_before": 30,
  "score_after": -45,
  "mate_in": null,
  "cp_loss": 75,
  "rating": "inaccuracy"
}
```
| Field | Meaning |
|---|---|
| `score_before` / `score_after` | evaluation before and after the move (White's POV); `null` if it's a forced mate |
| `mate_in` | signed int if there is a forced mate after the move (positive = White mates), else `null` |
| `cp_loss` | how much worse the move was than the best move, from the mover's side, ≥ 0 |
| `rating` | `"best"` (≤ 10), `"good"` (≤ 50), `"inaccuracy"` (≤ 100), `"mistake"` (≤ 300), `"blunder"` (> 300). Thresholds on `cp_loss`; Joel may tune them. |

Blocks ≤ 2 × `think_time_s`. Errors: `NO_GAME`, `ENGINE_ERROR`, `BAD_REQUEST` (no moves yet).

### 3.8 `GameEngine.resign(color: str) -> dict`
Ends the game: `result` = the other side wins, `termination` = `"RESIGNATION"`. Returns `state()`.

### 3.9 Fake engine
`FakeGameEngine` uses python-chess with no Stockfish: `get_engine_move()` and `get_hint()` return the first legal move (or a random one), and `rate_last_move()` always returns `"good"`. Everything else behaves the same.

### 3.10 Technical notes
- `sudo apt install stockfish` → `/usr/games/stockfish`. Bookworm ships Stockfish 15.1 (Elo range 1350–2850); Trixie ships 17 (1320–3190). That's why the range is read at start.
- Pi defaults: `Threads` 2 (leave cores for OpenCV), `Hash` 64 MB, think time 1–2 s.
- Don't set `MultiPV` or `Ponder` with `configure()`; python-chess manages them.
- `SimpleEngine` is thread-safe, but don't modify a `Board` while a call using it is running.

---

## 4. LED: Hsin-Chen

Two parts: the Python class on the Pi that main calls, and the serial protocol between the Pi and the Pico.

### 4.1 Pi side: `LedController`

| Method | Returns | Meaning |
|---|---|---|
| `start()` | `{"ok": true, "fw": "checkmate-led 1.0"}` or `LED_DISCONNECTED` | opens the serial port and sends `ping`. If it fails, the controller keeps retrying in the background; the game works without LEDs. |
| `show(squares: list)` | `{"ok": true}` / error | **replaces** everything lit with this list |
| `clear()` | `{"ok": true}` / error | all LEDs off |
| `set_brightness(percent: int)` | `{"ok": true}` / error | 0–100 |
| `self_test()` | `{"ok": true}` / error | lights a1, h1, h8, a8 one by one (about 2 s), to check orientation |
| `is_connected()` | bool | last command or ping succeeded |
| `close()` | None | |

**Every method returns within about 1.2 s and never raises.** If the Pico is unplugged, they return `LED_DISCONNECTED` and the game continues.

`squares` items:
```python
led.show([
    {"sq": "e7", "role": "engine_from"},
    {"sq": "e5", "role": "engine_to"},
])
```
| Field | Type | Meaning |
|---|---|---|
| `sq` | square | which square |
| `role` | role name (table below) | why it's lit; the role decides color and blink |

The same square must not appear twice.

### 4.2 Roles → colors

The Pico firmware owns this table (the Pi only sends role names, so colors can be changed in one place). On a single-color matrix every role is just "on", and `error` blinks.

| Role | Used for | Color (R,G,B) | Effect |
|---|---|---|---|
| `engine_from` | square the computer's piece moves from; also a piece the human must remove (en passant pawn) | `0, 0, 255` blue | steady |
| `engine_to` | square the computer's piece moves to | `0, 255, 0` green | steady |
| `hint_from` | hint source | `0, 255, 255` cyan | steady |
| `hint_to` | hint destination | `255, 255, 0` yellow | steady |
| `error` | squares that don't match (wrong move, wrong setup) | `255, 0, 0` red | blink 2 Hz |
| `check` | king in check | `255, 128, 0` orange | steady |
| `last_move` | last move played | `40, 40, 40` dim white | steady |

What main sends for the computer's move (`m = engine.get_engine_move()`):

| Move | Squares sent |
|---|---|
| Normal / capture | `m.from` → `engine_from`, `m.to` → `engine_to` |
| Castling | `m.from`, `m.rook_from` → `engine_from`; `m.to`, `m.rook_to` → `engine_to` |
| En passant | `m.from`, `m.capture_square` → `engine_from`; `m.to` → `engine_to` |
| Promotion | same as normal; UI tells the human which piece to put down |

### 4.3 Serial protocol (Pi ↔ Pico)

**Connection**
- USB cable, CDC serial. Pi opens `/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_*-if00` (glob it; fallback `/dev/ttyACM0`). The baud rate setting doesn't matter for USB CDC; use 115200.
- The Pi keeps the port open the whole time (DTR on). The Pico only sends output while a host has the port open.

**Framing**
- One JSON object per line, UTF-8/ASCII, ends with `\n`, max 512 bytes per line.
- The Pi sends **one command at a time** and waits for the reply with the same `id` before sending the next.
- `id`: int, starts at 1, +1 per command, wraps after 2³¹.
- The Pico answers **every** command with exactly one line.

**Timeouts and recovery**
- No reply within `reply_timeout_s` (0.5 s): resend once with the same `id`. Still nothing: mark disconnected, return `LED_DISCONNECTED`.
- While disconnected, the Pi sends `ping` every 2 s (and reopens the port if it disappeared). When the Pico answers, the Pi resends the last `set` so the LEDs show the right thing again.
- Every command sets the **full** LED state, so sending the same command twice is harmless.
- The Pico firmware lights nothing on boot, except that it may show a short boot animation for ≤ 1 s.

**Commands, Pi → Pico**

| `cmd` | Extra fields | Effect |
|---|---|---|
| `ping` | none | nothing; reply includes the firmware version |
| `clear` | none | all off |
| `set` | `squares`: list of `{"sq", "role"}` (same as `show`) | all off, then light these |
| `brightness` | `value`: int 0–100 | global brightness, %; keep the current pattern |
| `test` | none | a1 → h1 → h8 → a8, 0.5 s each, then off |

```json
{"id": 1, "cmd": "ping"}
{"id": 2, "cmd": "clear"}
{"id": 3, "cmd": "set", "squares": [{"sq": "e1", "role": "engine_from"}, {"sq": "h1", "role": "engine_from"}, {"sq": "g1", "role": "engine_to"}, {"sq": "f1", "role": "engine_to"}]}
{"id": 4, "cmd": "brightness", "value": 40}
{"id": 5, "cmd": "test"}
```

**Replies, Pico → Pi**
```json
{"id": 1, "ok": true, "fw": "checkmate-led 1.0"}
{"id": 3, "ok": true}
{"id": 6, "ok": false, "error": "BAD_SQUARE", "message": "z9"}
```
| Pico `error` | Meaning |
|---|---|
| `BAD_JSON` | line isn't valid JSON (reply `id` is `null`) |
| `BAD_CMD` | unknown `cmd` |
| `BAD_SQUARE` | square not `a1`–`h8` |
| `BAD_ROLE` | unknown role |
| `TOO_LONG` | line longer than 512 bytes (reply `id` is `null`) |

On the Pi, any Pico error becomes `{"ok": false, "error": "LED_REJECTED", "message": "<pico error>: <pico message>"}`.

**Square → LED index mapping**
The **Pico firmware** converts square names to LED indexes (wiring start corner, serpentine or not, rotation relative to the board). The Pi never sends LED indexes. Use `test` to check the mapping.

### 4.4 Fake LED
`FakeLedController` has the same methods, always returns `{"ok": true}`, and prints the board as an 8×8 text grid (rank 8 on top) with role letters, so teammates can see what would be lit.

### 4.5 Technical notes (from official docs)
- In `main.py` call `micropython.kbd_intr(-1)`, so a `0x03` byte in the data doesn't stop the program.
- Read input with `select.poll()` on `sys.stdin`, then `sys.stdin.read(1)` one character at a time. A known MicroPython bug makes `read()` with no size block.
- WS2812 (NeoPixel): `neopixel.NeoPixel(Pin(n), 64)`, `np[i] = (r, g, b)`, then `np.write()`. 64 LEDs can draw up to ~3.8 A at full white: use an **external 5 V supply** (shared ground with the Pico), a level shifter on the data line, and cap brightness in firmware.
- `mpremote` and the main program can't hold the serial port at the same time; stop main before uploading firmware.

---

## 5. UI: Jayden

The UI **shows state and sends commands**. It never decides anything about the game itself: no legal-move checking, no clock, no game state of its own.

### 5.1 Backend: FastAPI server (`checkmate/server.py`)

The backend is a **FastAPI** app run by uvicorn on the Pi:
```
uvicorn checkmate.server:app --host 127.0.0.1 --port 8000
```
Chromium opens `http://127.0.0.1:8000/` in kiosk mode. The server only listens on `127.0.0.1`, so it's not reachable from the network (change `host` to `0.0.0.0` only for debugging from a laptop).

| Method | Path | Request | Response | Purpose |
|---|---|---|---|---|
| `GET` | `/` and `/assets/...` | none | the UI's built files from `static_dir` (`ui/dist`) | serves the frontend (FastAPI `StaticFiles`, `html=True`) |
| `WS` | `/ws` | UI → server: command messages (5.5) | server → UI: `info`, `state`, `toast` messages (5.2, 5.3, 5.6) | **main channel**: live updates and commands |
| `GET` | `/api/info` | none | the `info` object (5.2) | same data as over WebSocket, for debugging |
| `GET` | `/api/state` | none | the current `state` object (5.3) | same data as over WebSocket, for debugging / first load |
| `POST` | `/api/command` | JSON body = one command (5.5) | `200 {"ok": true}` or `400 {"ok": false, "error": "BAD_REQUEST" \| "NOT_ALLOWED", "message": "..."}` | send a command without WebSocket (testing with `curl`) |
| `GET` | `/api/camera.jpg` | none | `image/jpeg` from `camera.get_debug_image()`, or `404` if no frame | camera-check screen |
| `GET` | `/api/health` | none | `{"ok": true, "devices": {"camera": "ok", "engine": "ok", "led": "error"}}` | quick device check |

Example with curl:
```
curl -X POST http://127.0.0.1:8000/api/command -H 'Content-Type: application/json' \
     -d '{"type": "start_game", "human_color": "white", "elo": 1500, "mode": "play"}'
```

**WebSocket rules (`/ws`)**
- Each text message is one JSON object with a `"type"` field.
- On connect, the server immediately sends `info`, then the current `state`. After that it sends a new full `state` **every time anything changes**. The UI always renders the newest `state` and never merges partial updates.
- Several clients may connect (e.g. the touchscreen plus a laptop for debugging); all get the same messages.
- If the connection drops, the UI reconnects every 1 s and shows "Connecting…" meanwhile.

**Threads inside the backend**
- uvicorn runs the FastAPI app (asyncio) in the main thread.
- The game loop (section 6) runs in **one background thread**, started in FastAPI's `lifespan` handler at startup and stopped at shutdown. That thread is the only one that calls `Camera`, `GameEngine` and `LedController`, so module code doesn't need locks.
- Commands from `/ws` or `/api/command` are checked for format, then put into a `queue.Queue`; the game loop takes them out.
- When the game loop builds a new `state`, it sends it to all WebSocket clients with `asyncio.run_coroutine_threadsafe(broadcast(state), loop)`. Never call module functions from `async` route handlers (they block).

**Frontend development (Jayden)**
- Develop on a laptop with the frontend's own dev server (e.g. Vite at `http://localhost:5173`), connecting to `ws://<pi-or-fake-server>:8000/ws`. The server enables CORS for `http://localhost:5173` in development.
- For the Pi, build the UI (`npm run build`) into `ui/dist/`; FastAPI serves it, so no Node.js is needed on the Pi.

### 5.2 Main → UI: `info` (once per connection)
```json
{ "type": "info", "version": "1", "elo_min": 1320, "elo_max": 3190, "engine_name": "Stockfish 17" }
```

### 5.3 Main → UI: `state`
```json
{
  "type": "state",
  "phase": "engine_move_pending",
  "mode": "play",
  "fen": "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
  "human_color": "black",
  "turn": "white",
  "elo": 1500,
  "moves_san": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],
  "last_move": "f8c5",
  "in_check": false,
  "engine_move": {
    "move": "e1g1", "san": "O-O", "from": "e1", "to": "g1",
    "rook_from": "h1", "rook_to": "f1", "capture_square": null, "promotion": null
  },
  "promotion": null,
  "hint": null,
  "rating": null,
  "board_problem": null,
  "result": null,
  "termination": null,
  "message": "Play the computer's move: O-O (e1→g1, rook h1→f1)",
  "devices": { "camera": "ok", "engine": "ok", "led": "ok" }
}
```
| Field | Type | Meaning |
|---|---|---|
| `phase` | str | see 5.4 |
| `mode` | `"play"` / `"practice"` / `null` | `null` before a game starts |
| `fen` | str or `null` | authoritative position (draw the board from this). `null` before a game starts |
| `human_color`, `turn` | color or `null` | |
| `elo` | int or `null` | |
| `moves_san` | list | move list for display |
| `last_move` | UCI or `null` | highlight on the on-screen board |
| `in_check` | bool | |
| `engine_move` | dict or `null` | set only in `engine_move_pending`; same fields as `get_engine_move()` (3.5) |
| `promotion` | dict or `null` | set only in `promotion_choice`: `{"from": "e7", "to": "e8", "choices": ["q","r","b","n"]}` |
| `hint` | dict or `null` | last requested hint, same fields as `get_hint()`; cleared after the next move |
| `rating` | dict or `null` | practice mode: rating of the human's last move, same fields as `rate_last_move()` (3.7) |
| `board_problem` | dict or `null` | physical board doesn't match: `{"squares": ["e2","e5"], "text": "Board doesn't match. Put the pieces back."}` |
| `result`, `termination` | | same as `engine.state()` |
| `message` | str | one short line to show the user |
| `devices` | dict | each of `camera`, `engine`, `led` is `"ok"` or `"error"` |

### 5.4 Phases: what the UI shows and which commands it may send

| `phase` | Meaning | UI shows | Commands allowed |
|---|---|---|---|
| `idle` | no game | start screen: color (white / black / random), difficulty (slider `elo_min`–`elo_max` or presets), mode (play / practice) | `start_game`, `calibrate` |
| `calibrating` | camera calibration running | spinner, "Put the pieces in the starting position" | none |
| `setup_check` | game created; waiting until the physical board matches the start position | "Set up the board"; wrong squares from `board_problem` | `cancel` |
| `human_turn` | waiting for the human's move | "Your move", hint button | `hint`, `resign`, `cancel` |
| `engine_thinking` | Stockfish is computing | spinner "Thinking…" | `resign`, `cancel` |
| `engine_move_pending` | LEDs show the computer's move; waiting for the human to play it on the board | `engine_move` big and clear (SAN + from→to, rook for castling, removed pawn for en passant, new piece for promotion) | `resign`, `cancel` |
| `promotion_choice` | human promoted a pawn; camera can't tell which piece | Q / R / B / N buttons | `promote`, `cancel` |
| `game_over` | game ended | `result`, `termination`, move list | `start_game`, `cancel` |
| `error` | camera or engine failed | `message`, `devices` | `retry`, `calibrate`, `cancel` |

`board_problem` can also be set in `human_turn` and `engine_move_pending` (illegal move or the computer's move played wrong). The phase stays the same; the UI shows a warning until it goes back to `null`.

### 5.5 UI → Main: commands

| `type` | Fields | Meaning |
|---|---|---|
| `start_game` | `human_color`: `"white"`/`"black"`/`"random"`, `elo`: int, `mode`: `"play"`/`"practice"` | new game → `setup_check` |
| `hint` | none | ask for a hint → `state.hint` is set and the hint squares light up |
| `promote` | `piece`: `"q"`/`"r"`/`"b"`/`"n"` | answer in `promotion_choice` |
| `resign` | none | human resigns → `game_over` |
| `cancel` | none | abandon the current game → `idle` |
| `calibrate` | none | run camera calibration → `calibrating` → `idle` |
| `retry` | none | in `error`: restart the failed device and continue |

```json
{ "type": "start_game", "human_color": "white", "elo": 1500, "mode": "practice" }
{ "type": "hint" }
{ "type": "promote", "piece": "q" }
{ "type": "resign" }
{ "type": "cancel" }
{ "type": "calibrate" }
{ "type": "retry" }
```

### 5.6 Main → UI: `toast` (short notification)
For a command that isn't allowed or is malformed, or a one-off event:
```json
{ "type": "toast", "level": "error", "text": "Hint is not available while the computer is thinking" }
```
`level`: `"info"`, `"warning"`, `"error"`. Show it for ~3 s. A rejected command does **not** change `state`. (Over `/api/command`, the same rejection comes back as HTTP `400` with `NOT_ALLOWED` or `BAD_REQUEST`.)

### 5.7 Fake backend
Until the real game loop is ready, the FastAPI server can run with **fake modules** (`FakeCamera`, `FakeGameEngine`, `FakeLedController`) on any laptop. It exposes the same endpoints (5.1). In addition, a debug-only endpoint `POST /api/fake/state` (body = a `state` object) broadcasts that state as-is, so Jayden can show every phase in 5.4 (including `board_problem`, `promotion`, `rating`, `game_over`) without playing a game. The fake server logs every command it receives.

---

## 6. Main loop (how it's all glued together)

The game loop runs in its own thread inside the FastAPI backend (5.1), at about **10 Hz**. UI commands arrive from `/ws` or `/api/command` through a `queue.Queue`; the loop processes them at the top of each iteration. After any change, it builds a new `state` (5.3) and broadcasts it to all WebSocket clients.

```
idle
  start_game ─▶ engine.new_game(color, elo, mode) ─▶ setup_check

setup_check
  every stable observation:
    obs.occupancy == occupancy_from_fen(START_FEN)?
      yes ─▶ led.clear() ─▶ human_turn (human is white) / engine_thinking (human is black)
      no  ─▶ board_problem = differing squares, led.show(those squares as "error")

human_turn
  wait for a stable observation whose occupancy differs from the last one processed
  r = detect_move(engine.state().fen, obs.occupancy)
    move       ─▶ engine.push_move(r.move); led.clear()
                  practice mode: rating = engine.rate_last_move()
                  game over? ─▶ game_over, else ─▶ engine_thinking
    promotion  ─▶ promotion_choice
    no_change  ─▶ clear board_problem, stay
    invalid    ─▶ board_problem = r.changed_squares, led.show(… "error"), stay
                  (the human fixes the board; the next stable observation is checked again)
  hint ─▶ hint = engine.get_hint(); led.show(hint_from / hint_to)

promotion_choice
  promote(piece) ─▶ engine.push_move(from + to + piece) ─▶ same as "move" above

engine_thinking
  m = engine.get_engine_move()                       (blocks ~1 s)
    ok    ─▶ led.show(squares from table 4.2) ─▶ engine_move_pending
    error ─▶ error phase (retry restarts engine and asks again)

engine_move_pending
  r = detect_move(engine.state().fen, obs.occupancy) on each new stable observation
    r is m.move (or promotion candidates contain m.move)
          ─▶ engine.push_move(m.move); led.clear()
             game over? ─▶ game_over, else ─▶ human_turn
    no_change ─▶ stay (human hasn't moved yet)
    anything else ─▶ board_problem = wrong squares, LEDs keep showing m plus "error" squares, stay

game_over
  led.clear(); wait for start_game or cancel
```

Device failures:
- **Camera** `CAMERA_NOT_READY` → `error` phase. `retry` calls `camera.start()` again; `calibrate` runs calibration.
- **Engine** `ENGINE_ERROR` → `error` phase. `retry` calls `engine.close()`, `engine.start()`, then retries the same step. The board state is kept by python-chess, so nothing is lost.
- **LED** `LED_DISCONNECTED` → **not** an error phase. `devices.led = "error"`; the game continues and the UI shows the computer's move on screen.
