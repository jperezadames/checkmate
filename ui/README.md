# CheckMate touchscreen UI

Owner: Jayden. React + TypeScript + Vite, designed for an **800×480 landscape touchscreen**.

## Develop on your laptop

Use Node.js 22.12+ (a current LTS release is recommended). From the repository root:

```bash
cd ui
npm install
npm run dev
```

Open http://localhost:5173. The dev server updates the browser when you save changes.

The page connects to the backend's WebSocket at `ws://127.0.0.1:8000/ws` and shows its live state. Start the backend from the repository root, with fake modules if there's no hardware (see [`../RUNNING.md`](../RUNNING.md)):

```bash
CHECKMATE_FAKE=all .venv/bin/uvicorn checkmate.server:app
```

- `?mock=1` shows the sample data instead, with the **Preview state** picker; no backend needed.
- `?backend=<host>:<port>` connects to another backend, e.g. the Pi's (its server must listen on `0.0.0.0` then).

The development view includes an 800×480 frame when the browser is at least 848 CSS pixels wide. Smaller windows reflow for usability rather than pretending to be an exact-size preview. Use 100% browser zoom to inspect the intended CSS dimensions; physical size varies by laptop display.

Click **Fill window** to hide the preview frame; reload to restore it. To check the actual kiosk layout, open http://localhost:5173/?preview=0 and set the browser's responsive viewport to 800×480. `?preview=1` explicitly enables the frame, including in a production preview.

## Rotary navigation + Select

The product uses a rotary encoder and one Select button. Counterclockwise sends `ArrowLeft`, clockwise sends `ArrowRight`, and Select sends `Enter`. On a laptop, use Left, Right, and Enter.

- Rotation moves the gold highlight through enabled controls in a fixed document order, wrapping at either end. Controls need not share a row. Turning never activates an action.
- Setup has two separate screens: **Choose your color**, then **Choose your difficulty**. Selecting a color advances; selecting a difficulty marks it, and **Start game** confirms. **Back to color** preserves the selections; **Menu** leaves setup.
- Every screen/dialog has a selectable Menu, Back, Close, Keep Playing, or Leave control. Escape is optional on a laptop and is never needed by the hardware flow.
- The game starts focused on Settings. Turn to reach Hint (live human turn), move history, and Leave. Promotion starts on Queen, game over on Play Again, and device errors on Try Again. Disabled controls are skipped.
- Select toggles settings checkboxes. Holding Select does not repeatedly activate actions.
- Select move history to browse, turn to scroll backward/forward, and Select again to finish. Then rotation resumes control navigation.
- Dialogs contain navigation and restore the previous focus when closed. Mouse, touch, and Tab still work.
- Laptop preview controls remain outside rotary navigation.
- Select the circular arrow in the header to rotate the entire display 180°. The orientation is remembered across screens and reloads.

### Physical input integration

Chromium receives ordinary keyboard events from the Pi. The `checkmate-rotary` service translates encoder detents into Left/Right key taps, and the Pi's `gpio-key` overlay sends Enter for Select. Follow the [Pi wiring and installation steps](../pi-setup.txt) and keep Chromium focused.

## Current behavior

- The screen always shows the backend's newest `state`; the UI decides nothing about the game. Any phase but `idle` shows the game screen, also after a reload in the middle of a game. While the connection is down it shows **Connection lost** with the last position, and reconnects every second.
- Play vs Bot opens color/difficulty setup, then **Start game** sends `start_game`. The difficulty presets use the engine's Elo range from `info`. If the camera isn't calibrated, the setup screen says so and offers **Calibrate camera**.
- The game screen sends `hint` (button on your turn), `promote`, `resign`, `retry` and `calibrate` (device error), and `cancel` when leaving or before **Play again**. Toasts from the backend appear at the top for 3 s.
- Live and sample screens both use rotary navigation plus Select, including the two-step setup flow.
- With a fake camera on the backend (`CHECKMATE_FAKE=camera,...`), you play by clicking the screen's board: a piece, then its square (yours on your turn, the computer's while it waits for you). The backend checks the move and the fake camera "sees" it. Above the frame, **Start position** resets the fake board and **Play the computer's move** plays the pending one. With a real camera the board is display-only.
- The rest of this list describes the sample mode (`?mock=1`).
- Play vs Bot opens color/difficulty setup, then **Open game preview** displays an illustrative game snapshot. The board is a display of the physical game, not a place to drag pieces.
- The game view includes a board, evaluation bar, turn/bot-move instructions, latest-move rating, and scrollable move history.
- Use **Preview state** above the touchscreen frame to inspect your turn, bot thinking, pending bot move, check, mismatch, promotion, game over, connection loss, setup, device failure, and unavailable analysis. There is also a sample mistake rating. These snapshots do not advance automatically or play a legal game.
- Pending bot moves highlight their squares but do not move on-screen pieces before confirmation. The production backend will provide that confirmation and the next full snapshot.
- Game settings can hide evaluation/feedback, flip the board, or open confirmations for resigning and leaving. Promotion, resignation, retry, and Play Again only update the local preview/navigation.
- Setup uses the contract's current Elo presets; live engine limits will replace those defaults during integration. Random color is resolved locally only for this sample preview.
- Training currently opens an informational dialog describing its future screens.
- Puzzles is visible, labeled “Coming later,” and disabled.
- All game positions and scores are clearly labeled sample data. There are no backend calls, locally validated moves, or real chess engine in the frontend.
- Training will include feedback plus an Ask Trainer conversation screen. Its chat API still needs agreement with the team.

## Check and build

```bash
npm run typecheck
npm test
npm run build
npm run preview
```

`build` also checks TypeScript, then writes static files into `ui/dist/`. `preview` serves the build locally (usually http://localhost:4173), filling the browser like the deployed app.

On the Pi, build/copy `ui/dist/` before starting the team's FastAPI server. It serves the frontend at http://127.0.0.1:8000/; Node.js isn't required on the Pi to serve a completed build. Generated `dist/` and `node_modules/` are not committed.

## Structure and integration

- `src/screens/MainMenu.tsx` — available modes and menu copy.
- `src/screens/GameSetup.tsx` — color and bot difficulty selection.
- `src/screens/GameScreen.tsx` — phase-driven game layout and display preferences.
- `src/screens/GameScreen.css` — game, setup, and dialog layout.
- `src/components/` — shared frame, board, analysis, move list, status, buttons, dialogs, and laptop preview.
- `src/components/DirectionalNavigation.tsx` — shared focus, arrow movement, Enter activation, and modal boundaries.
- `src/navigation/spatial.ts` — earlier spatial-navigation helper, unused by rotary navigation.
- `src/types/game.ts` — types for full contract state snapshots.
- `src/mocks/gameStates.ts` — sample positions, scores, and phase snapshots, isolated from presentation components.
- `src/styles/theme.css` — colors and shared design tokens.
- `src/screens/MainMenu.css` — menu layout and interaction states.
- `src/App.tsx` — the live app: navigation from the backend's phase, buttons → commands. `?mock=1` renders `src/PreviewApp.tsx` instead (sample data, local preview actions).
- `src/backend.ts` — `useBackend()`: the WebSocket, reconnecting, newest `info` / `state`, toasts, `send(command)`, and the fake board (`fakeCamera`, `fakeBoard(...)`).
- `src/keys.ts` — earlier four-button helper, unused; `DirectionalNavigation` handles rotary input.

Contract: `../contracts/interfaces.md`, section 5. The UI renders full backend state snapshots and sends allowed commands via `/ws`. Game logic remains on the backend. The menu uses the contract's `play` and `practice` mode names. The evaluation and rating additions agreed with Jayden (section 5.3.1) are sent by the backend.

Not done yet: the Training mode, and lighting the hint squares on the on-screen board (the hint is shown as text and on the LEDs).
