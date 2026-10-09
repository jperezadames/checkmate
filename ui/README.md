# Touchscreen UI

Owner: Jayden. Contract: `contracts/interfaces.md` section 5 (API 5.1, `state` 5.3, phases 5.4, commands 5.5).

- Any frontend framework. Develop with its dev server (e.g. Vite on `http://localhost:5173`), connecting to `ws://<backend>:8000/ws`.
- Build into `ui/dist/`; the FastAPI backend serves it at `http://127.0.0.1:8000/`, so the Pi doesn't need Node.js.
