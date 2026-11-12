# Running CheckMate

How to start the system, on a laptop without the hardware or on the Raspberry Pi, and how to play and check it from a terminal.
Installing: [README](README.md#development-setup). Setting up the Pi: [`pi-setup.txt`](pi-setup.txt). The API: [`contracts/interfaces.md`](contracts/interfaces.md) section 5.

## What runs

One process, started from the repository root:

```bash
.venv/bin/uvicorn checkmate.server:app --host 127.0.0.1 --port 8000
```

It runs:
- the FastAPI server: HTTP and the WebSocket `/ws` on http://127.0.0.1:8000 (contract section 5.1);
- the game loop in a background thread. It opens the camera, Stockfish and the LED matrix (over SPI), and closes them on Ctrl+C;
- the UI's built files from `ui/dist/` at `/`, if that folder exists. Otherwise `/` is a 404 and the API still works.

## Real or fake modules

Set these in front of the command; they apply to that one run.

| Variable | Value | Effect |
|---|---|---|
| `CHECKMATE_FAKE` | not set | every module is real (the Pi) |
| | `all` | `FakeCamera`, `FakeGameEngine`, `FakeLedController` |
| | some of `camera,engine,led` | only those are fake |
| `CHECKMATE_CONFIG` | a file path | read this config instead of `config.json` |

With any fake module, the debug routes `/api/fake` (which modules are fake), `/api/fake/state` and `/api/fake/board` are available (contract section 5.7). The fake LED prints what would be lit as a grid in the server's terminal.

## On a laptop

Stockfish: `brew install stockfish` (macOS) or `sudo apt install stockfish` (Linux). Without it, use `CHECKMATE_FAKE=all`.

`config.json` has the Pi's Stockfish path (`/usr/games/stockfish`). On a Mac, make a copy with the Homebrew path once. `config.local.json` is git-ignored:

```bash
sed 's#/usr/games/stockfish#/opt/homebrew/bin/stockfish#' config.json > config.local.json
```

Then start one of these:

```bash
# real Stockfish, fake camera and LEDs: the most useful one
CHECKMATE_FAKE=camera,led CHECKMATE_CONFIG=config.local.json .venv/bin/uvicorn checkmate.server:app
```

```bash
# everything fake, no Stockfish needed
CHECKMATE_FAKE=all .venv/bin/uvicorn checkmate.server:app
```

```bash
# the laptop's webcam too: asks for camera permission, needs the ArUco markers and a calibration (see the Pi section)
CHECKMATE_FAKE=led CHECKMATE_CONFIG=config.local.json .venv/bin/uvicorn checkmate.server:app
```

Stop the server with Ctrl+C. If port 8000 is taken, add `--port 8001` and use that port below.

### Play a game with the fake camera

Commands go to `/api/command`. A move on the "board" goes to `/api/fake/board`; the fake camera then sees it the way the real one would. In a second terminal:

```bash
# new game, you play white
curl -X POST localhost:8000/api/command -H 'Content-Type: application/json' \
     -d '{"type": "start_game", "human_color": "white", "elo": 1500, "mode": "play"}'

# your move
curl -X POST localhost:8000/api/fake/board -H 'Content-Type: application/json' -d '{"move": "e2e4"}'

# the state: phase, message, engine_move, rating, evaluation, ...
curl -s localhost:8000/api/state | python3 -m json.tool

# play the computer's move (state.engine_move.move) on the board for it
curl -s -X POST localhost:8000/api/fake/board -H 'Content-Type: application/json' \
     -d "{\"move\": \"$(curl -s localhost:8000/api/state | python3 -c 'import json,sys; print(json.load(sys.stdin)["engine_move"]["move"])')\"}"
```

Then repeat: your move, the computer's move. The other commands work the same way: `{"type": "hint"}`, `{"type": "resign"}`, `{"type": "cancel"}`, and `{"type": "promote", "piece": "q"}` when the phase is `promotion_choice`. Contract section 5.4 lists which phase allows which command.

Other bodies for `/api/fake/board`:

| Body | The fake camera sees |
|---|---|
| `{"move": "e2e4"}` | the position in `state.fen` after that move |
| `{"fen": "<FEN>"}` | that position. **Before a second game**, send the start position (`rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`): the fake board keeps the last game's position, so the setup check would wait |
| `{"occupancy": "..."}` | any 64 characters of `W`, `B`, `.` (contract section 1.2), e.g. a wrong board to see `board_problem` |
| `{"stable": false}` | a hand over the board: nothing is read until `{"stable": true}` |

### Watch the WebSocket

```bash
.venv/bin/python -m websockets ws://127.0.0.1:8000/ws
```

This prints every `info`, `state` and `toast` message as the UI receives them. Type a command as one line of JSON to send it.

### The UI

With the backend running, start the UI's dev server and open http://127.0.0.1:5173. It connects to `ws://127.0.0.1:8000/ws` and shows the live game. With the fake camera, make the moves by clicking the screen's board (a piece, then its square; the computer's move too), or with the **Start position** / **Play the computer's move** buttons above it. The UI uses a rotary encoder plus Select: turn to move the highlight and press Select to activate. On a laptop, use ← → and Enter. Setup walks through color, difficulty, then the game. Select on-screen Back/Close controls to return:

```bash
cd ui && npm install && npm run dev
```

Or build it once (`cd ui && npm run build`) and restart the backend: it then serves the UI itself at http://127.0.0.1:8000/, like on the Pi. `?mock=1` shows sample data without a backend; `POST /api/fake/state` shows any phase with the live UI. More in [`ui/README.md`](ui/README.md).

## On the Raspberry Pi

Once:
1. Follow [`pi-setup.txt`](pi-setup.txt) to install Stockfish, set up the venv, and configure the rotary encoder and Select button.
2. Wire the WS2812 matrix's data line to SPI MOSI (GPIO10, pin 19) through a level shifter, enable SPI (`dtparam=spi=on`), and power the strip from an external 5 V supply (see [`pi-setup.txt`](pi-setup.txt)).
3. Build the UI on a laptop (`cd ui && npm run build`) and copy `ui/dist/` to the Pi. Node.js isn't needed on the Pi.
4. Print the calibration markers (`.venv/bin/python scripts/camera/make_aruco_markers.py`) and place them just outside the corners: id 0 at a1, 1 at h1, 2 at h8, 3 at a8. Or set `camera.manual_corners` in `config.json` instead.

Start the server (every module real), then open http://127.0.0.1:8000/ in Chromium in kiosk mode (`chromium --kiosk http://127.0.0.1:8000/`; on Bookworm the command is `chromium-browser`):

```bash
.venv/bin/uvicorn checkmate.server:app --host 127.0.0.1 --port 8000
```

**First run: calibrate the camera.** Without `calibration.json`, the start screen says the camera isn't calibrated and `devices.camera` is `"error"`. Put the pieces in the starting position, then press Calibrate in the UI, or:

```bash
curl -X POST localhost:8000/api/command -H 'Content-Type: application/json' -d '{"type": "calibrate"}'
```

It is saved to `calibration.json` and loaded on every later start. Calibrate again whenever the camera or the board moves.

**Check the devices:**

```bash
curl -s localhost:8000/api/health                    # {"ok": true, "devices": {"camera": "ok", "engine": "ok", "led": "ok"}}
curl -s localhost:8000/api/camera.jpg -o board.jpg   # what the camera sees, with the grid and the detections
```

To aim the camera before starting the server, use `.venv/bin/python scripts/camera/preview.py` (c = calibrate, q = quit). Stop the server first: only one program can hold the camera.

## When something is wrong

| You see | Why | What to do |
|---|---|---|
| phase `error`, "Engine problem: could not start Stockfish at ..." | Stockfish isn't installed, or is at another path | install it; on a laptop use `CHECKMATE_CONFIG` (above); then Retry |
| phase `error`, "Camera problem: ..." | camera unplugged, or no frames for a few seconds | check the cable, then Retry; Calibrate if it moved |
| start screen: "The camera isn't calibrated" | no `calibration.json` yet | calibrate (above) |
| `devices.led` is `"error"`, the game goes on | SPI isn't enabled, no permission for `/dev/spidev0.0`, or the matrix isn't wired/powered | enable SPI (`dtparam=spi=on`), check wiring/power. It reconnects by itself within about 2 s; until then the UI shows the computer's moves |
| the setup check never ends | the board isn't in the starting position (`board_problem.squares` says where); with the fake camera, the last game's position | fix those squares; with the fake camera, send the start FEN to `/api/fake/board` |
| `/` returns 404 | no `ui/dist/` | build the UI, or use the API directly |
| `address already in use` | another server is on port 8000 | stop it, or use `--port` |
| a command gets `400 NOT_ALLOWED` | not allowed in the current phase (contract section 5.4); "(starting)" means the game loop is still opening the devices | check `phase` in `/api/state`; right after starting, wait until `/api/state` answers |

Retry from a terminal:

```bash
curl -X POST localhost:8000/api/command -H 'Content-Type: application/json' -d '{"type": "retry"}'
```

## Tests

```bash
.venv/bin/pytest
```

None of them need the hardware. The tests that use the real Stockfish are skipped when it isn't installed.
