# CheckMate - Proposal

## 1. Team Information
- **Team Name:** CheckMate
- **Team Members:**
  - **Harry Zhang (qianyongzhang@brandeis.edu)** – Camera Input Detection
  - **Jayden DeCambre (jdecambre@brandeis.edu)** – Touch Screen UI
  - **Joel Perez-Adames (joelperezadames@brandeis.edu)** – Stockfish API
  - **Hsin-Chen Hu (hhu@brandeis.edu)** – LED Board Synchronization
  - **Everyone** – 3D Printing & Trainer Implementation
- **Github Repository:** https://github.com/jperezadames/checkmate

## 2. Abstract
CheckMate is a smart physical chessboard designed to combine traditional over-the-board chess with modern embedded technology. The project addresses the gap between the tactile experience of playing with physical chess pieces and the interactive features normally available only through digital chess platforms. A camera mounted above the board will monitor the position of the physical pieces and convert the board image into a top-down 8×8 grid. By comparing the board before and after a move, the system will detect and validate player moves.

The system will use Stockfish as its chess engine for legal move management, computer play, and adjustable difficulty. An 8×8 LED matrix will provide visual guidance by identifying the source and destination squares for the computer's moves, which the player will physically execute. A touchscreen will provide game setup, practice modes, and move feedback. The project will also explore an AI-based conversational trainer that can provide move analysis, explanations, advice, and interactive assistance. A 3D-printed enclosure and camera stand will integrate the hardware into a complete prototype. The expected outcome is a playable smart chessboard that supports both competitive play and interactive learning.

## 3. Objectives
The main objectives of this project are:
- Create a physical smart chessboard that preserves the experience of playing with real chess pieces.
- Detect changes to the physical chessboard using an overhead camera.
- Convert the camera view into a top-down 8×8 representation of the board.
- Detect and validate moves by comparing the board state before and after each move.
- Integrate Stockfish for chess-engine functionality, legal moves, and adjustable difficulty/Elo.
- Synchronize an 8×8 LED matrix with the game state to show the source and destination squares of computer moves.
- Create a touchscreen interface for game setup, difficulty selection, practice modes, and move feedback.
- Implement training features such as puzzles, hints, move ratings, and engine-based analysis.
- Explore an AI conversational trainer that can explain moves and answer player questions.
- Design and 3D print an enclosure and camera stand that integrate the hardware into a usable prototype.

## 4. Proposed Solution
CheckMate will combine camera-based board detection, an embedded controller, LED feedback, a touchscreen interface, a chess engine, and an optional AI trainer into one physical chess system. The player will make moves normally on a physical board. The camera will observe the board from above and the software will determine how the board state has changed. Stockfish will manage legal moves and generate computer responses at a selected difficulty. Because the system does not physically move the pieces, the player remains “in the loop”: LEDs will identify the computer move's source and destination squares, and the player will execute that move on the board. The camera will then confirm that the move was completed correctly before the next turn begins.

### 4.1 Project Description
The project is centered on a physical chessboard augmented with digital sensing and feedback.

An overhead camera will continuously monitor all 64 squares. The camera image will be processed into a top-down 8×8 grid so that the system can compare the position before and after each move. This comparison will be used for move detection and validation.

Stockfish will provide the chess-engine portion of the system. It will support game management, legal move handling, computer move generation, and customizable difficulty through adjustable Elo. This allows CheckMate to support competitive play against a computer opponent at different skill levels.

For computer turns, an 8×8 LED matrix associated with the board will provide visual guidance. The LEDs will identify the source and destination squares of the move selected by the engine. The human player will physically move the computer's piece, and the overhead camera will confirm that the requested move was completed correctly before play continues.

A touchscreen will act as the primary user interface. During game setup, the player will be able to choose a bot difficulty and see whose turn it is. Practice modes will include ideas such as mate-in-two puzzles, training with hints, and move feedback. Engine analysis can be used to review the previous move and show a better option.

The trainer portion of the project will extend this feedback into interactive learning. The planned trainer will provide real-time move analysis and explanations, advice, questions, and conversational assistance. This is intended to make the board useful not only for playing games, but also for learning from them.

The physical system will be housed in a 3D-printed enclosure that hides the wiring beneath the board while remaining accessible. A 3D-printed camera stand will keep the camera fixed above the board with all 64 squares visible. The enclosure and stand will be measured, tested, printed, and assembled after the required hardware dimensions and camera view have been confirmed.

### 4.2 Hardware Components
| Component | Description | Quantity |
|---------|-------------|----------|
| Raspberry Pi Pico | Embedded controller for the physical system | 1 |
| 8×8 LED Matrix | Provides visual guidance for source and destination squares | 1 |
| Touchscreen | User interface for game setup, practice modes, and move feedback | 1 |
| Camera | Monitors the physical chessboard from above for board-state and move detection | 1 |
| 3D-Printed Container / Enclosure | Houses the board electronics and hides wiring while keeping components accessible | 1 |
| 3D-Printed Camera Stand | Holds the camera steadily above all 64 squares | 1 |

- **Schematic / physical arrangement:** The camera will be fixed above the chessboard. The 8×8 LED matrix will be synchronized with the board to indicate moves. The touchscreen will be positioned beside the board for game controls and training feedback. Wiring and electronics will be contained beneath the board in the 3D-printed enclosure.

### 4.3 Software Components
- **Libraries / Frameworks:**
  - Stockfish chess engine/API for move generation, legal moves, game management, analysis, and adjustable difficulty.
  - Camera/board-processing software for converting the camera view into an 8×8 board representation and detecting changes between positions.
  - Trainer software for move explanations, advice, questions, and conversational feedback.
- **Communication Protocols:** Specific protocols between the Pico, touchscreen, camera, and other components are still to be determined during hardware selection and integration.
- **Software Structure:**
  - Camera input and board-processing module
  - Move detection and validation module
  - Shared game-state representation
  - Stockfish/game-management module
  - LED synchronization module
  - Touchscreen user-interface module
  - Training and feedback module
- **Data Flow:**
  1. The camera captures the physical chessboard.
  2. The camera image is converted into a top-down 8×8 grid.
  3. The current board is compared with the previous board state to identify a move.
  4. The move is validated and the shared game state is updated.
  5. Stockfish processes the position and generates the computer response or analysis.
  6. The LED matrix identifies the source and destination squares of the computer move.
  7. The player physically executes the computer move.
  8. The camera confirms that the move was completed correctly before the next turn begins.
  9. The touchscreen displays game information, feedback, practice features, and training assistance.
- **User Interface:** The touchscreen will support game setup, bot difficulty selection, turn information, puzzles, training with hints, move feedback, and engine analysis. The trainer may additionally provide conversational explanations and assistance.

## 5. Methodology
1. **Requirement analysis**
   - Choose and confirm the required hardware.
   - Test the camera view to ensure all 64 squares are visible.
   - Agree on a shared game-state format so that the camera, Stockfish, LEDs, touchscreen, and trainer can exchange consistent information.

2. **Hardware setup**
   - Mount and test the overhead camera.
   - Set up the 8×8 LED matrix and touchscreen.
   - Measure the physical components and chessboard.
   - Design the board enclosure and camera stand in CAD.
   - Print and assemble the enclosure after fit and camera-view testing.

3. **Software development**
   - Develop the camera input and board-processing pipeline.
   - Implement move detection by comparing consecutive board states.
   - Integrate Stockfish for legal moves, computer play, adjustable difficulty, and analysis.
   - Develop the touchscreen interface.
   - Implement LED-board synchronization.
   - Develop practice features such as puzzles, hints, and move ratings.
   - Explore LLM-based explanations and conversational trainer functionality.

4. **Integration and testing**
   - Connect the camera, shared game state, Stockfish, LED guidance, and touchscreen into a complete game loop.
   - Confirm that the system correctly recognizes player moves and computer moves.
   - Test full chess games, including special moves.
   - Test the enclosure, camera alignment, and physical usability.
   - Identify and fix software and hardware bugs.

5. **Deployment / demonstration**
   - Assemble the complete prototype.
   - Perform full-game testing.
   - Rehearse the final demonstration and verify that the major play and training features work together.

## 6. Timeline
| Phase | Activities | Duration |
|------|------------|----------|
| Phase 1 – Plan & Test | Choose hardware, test camera view, and agree on a shared game-state format | Week 1 |
| Phase 2 – Build in Parallel | Develop camera + LEDs, Stockfish integration, touchscreen UI, and enclosure CAD in parallel | Weeks 2–3 |
| Phase 3 – Playable Game | Connect the game loop, set bot difficulty, and print/assemble the base and camera stand | Weeks 4–5 |
| Phase 4 – Practice Modes | Add puzzles, hints, move ratings, and optional LLM explanations | Weeks 6–7 |
| Phase 5 – Test & Demo | Full-game testing, special-move testing, bug fixes, and demo rehearsal | Week 8 |

## 7. Expected Outcomes
- A functional prototype of a smart physical chessboard.
- Reliable overhead monitoring of the physical board and conversion to an 8×8 representation.
- Move detection and validation based on changes in board state.
- A playable game loop using Stockfish for legal moves and computer play.
- Adjustable computer difficulty/Elo.
- LED guidance that clearly identifies the source and destination squares for computer moves.
- Camera confirmation that the player has correctly executed the requested computer move.
- A touchscreen interface for setup, turn information, practice modes, and move feedback.
- Practice features such as puzzles, hints, move ratings, and engine analysis.
- If feasible within the project schedule, AI-generated explanations and conversational training assistance.
- A 3D-printed enclosure and camera stand that organize the electronics and create a complete demonstration-ready system.
- Successful full-game testing, including special moves, before the final demonstration.

## 8. Conclusion
CheckMate combines the familiarity of a traditional physical chessboard with the capabilities of modern embedded and software systems. By using an overhead camera for move detection, LEDs for physical guidance, Stockfish for game management and adjustable computer play, a touchscreen for interaction, and an optional conversational trainer for learning, the project can support both competitive play and chess practice without replacing the physical pieces with a fully digital board.

The project is structured so that its major components can be developed in parallel and integrated through a shared game-state format. The eight-week roadmap progresses from hardware selection and individual subsystem development to a playable game, practice features, full-game testing, and a final demonstration. This modular approach makes the proposed system feasible while also allowing advanced trainer features to be added as time permits.

## References
1. Cornell ECE 4760 Fall 2025 project: https://ece4760.github.io/Projects/Fall2025/sl2847_zrs29_khy32/index.html
2. Vatsalparsaniya, *Realtime-OpenCV-Chess*: https://github.com/Vatsalparsaniya/Realtime-OpenCV-Chess
3. Stockfish Chess Engine: https://stockfishchess.org/
4. *Minimal Chess Set* on Printables: https://www.printables.com/model/878156-minimal-chess-set

## Development Setup

Python 3.10+. Dependencies are listed in `requirements.txt` (runtime) and `requirements-dev.txt` (runtime + tests). Use either pip or [uv](https://docs.astral.sh/uv/).

### Laptop

```bash
# pip
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# or uv
uv venv
uv pip install -r requirements-dev.txt
```

### Raspberry Pi

The Pi camera is used through Picamera2, which must come from apt. Create the venv with `--system-site-packages` so it stays visible (`numpy<2` in `requirements.txt` keeps it compatible).

```bash
sudo apt install python3-picamera2 stockfish

# pip
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

# or uv
uv venv --system-site-packages
uv pip install -r requirements.txt
```

### Run

```bash
# tests
.venv/bin/pytest            # or: uv run pytest

# backend server (http://127.0.0.1:8000)
.venv/bin/uvicorn checkmate.server:app --host 127.0.0.1 --port 8000
# or: uv run uvicorn checkmate.server:app --host 127.0.0.1 --port 8000
```

### Layout

Each module is a package under `checkmate/`; import from the package (`from checkmate.camera import Camera`), not from the files inside it. See `contracts/interfaces.md` section 0.4.

```
checkmate/
├── config.py            load_config()
├── errors.py            err(code, message), shared error result
├── camera/              Harry: Camera, FakeCamera, detect_move, occupancy_from_fen
├── engine/              Joel: GameEngine, FakeGameEngine
├── led/                 Hsin-Chen: LedController, FakeLedController
├── server/              FastAPI app (app.py) and /api routes (api.py)
└── game/                game loop (loop.py), not implemented yet
pico/main.py             Hsin-Chen: Pico LED firmware
ui/                      Jayden: frontend, built into ui/dist/
scripts/<module>/        manual tools (not used at runtime)
tests/<module>/          pytest tests
contracts/interfaces.md  interface contracts between modules
config.json              one section per module
```
