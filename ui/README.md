# CheckMate touchscreen UI

Owner: Jayden. React + TypeScript + Vite, designed for an **800×480 landscape touchscreen**.

## Develop on your laptop

Use Node.js 22.12+ (a current LTS release is recommended). From the repository root:

```bash
cd ui
npm install
npm run dev
```

Open http://localhost:5173. The dev server updates the browser when you save changes. No camera, LEDs, engine, backend, or touchscreen is needed for the UI preview.

The development view includes an 800×480 frame when the browser is at least 848 CSS pixels wide. Smaller windows reflow for usability rather than pretending to be an exact-size preview. Use 100% browser zoom to inspect the intended CSS dimensions; physical size varies by laptop display.

Click **Fill window** to hide the preview frame; reload to restore it. To check the actual kiosk layout, open http://localhost:5173/?preview=0 and set the browser's responsive viewport to 800×480. `?preview=1` explicitly enables the frame, including in a production preview.

## Current behavior

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
- `src/types/game.ts` — types for full contract state snapshots.
- `src/mocks/gameStates.ts` — sample positions, scores, and phase snapshots, isolated from presentation components.
- `src/styles/theme.css` — colors and shared design tokens.
- `src/screens/MainMenu.css` — menu layout and interaction states.
- `src/App.tsx` — navigation and local preview actions; replace its mock state source when wiring the backend.

Contract: `../contracts/interfaces.md`, section 5. Future integration will render full backend state snapshots and send allowed commands via `/ws`. Game logic remains on the backend. The menu uses the contract's `play` and `practice` mode names. The evaluation and rating additions agreed with Jayden are documented in section 5.3.1; the engine/backend owners still need to implement them. Their modules have not been changed by this UI work.
