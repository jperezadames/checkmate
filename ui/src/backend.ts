import { useCallback, useEffect, useRef, useState } from 'react';
import type { Command, GameState, Info, Toast } from './types/game';

/** The backend (§5.1). Served by FastAPI it is the same host; under the Vite dev server it is
 *  the backend on port 8000. `?backend=host:port` points somewhere else (e.g. the Pi). */
function backendHost(): string {
  return new URLSearchParams(window.location.search).get('backend')
    ?? (import.meta.env.DEV ? '127.0.0.1:8000' : window.location.host);
}

const secure = window.location.protocol === 'https:';

export function backendUrl(): string {
  return `${secure ? 'wss' : 'ws'}://${backendHost()}/ws`;
}

function apiUrl(path: string): string {
  return `${secure ? 'https' : 'http'}://${backendHost()}${path}`;
}

/** What the fake camera sees (§5.7): a move from `state.fen`, or a whole position. */
export type FakeBoard = { move: string } | { fen: string };

const RECONNECT_MS = 1000;
const TOAST_MS = 3000;

export interface Backend {
  connected: boolean;
  info: Info | null;
  /** Newest full state; kept while reconnecting, so the last confirmed position stays visible. */
  state: GameState | null;
  toasts: (Toast & { id: number })[];
  send: (command: Command) => void;
  /** The backend runs with a fake camera, so moves are made with `fakeBoard` instead of real pieces. */
  fakeCamera: boolean;
  fakeBoard: (board: FakeBoard) => void;
}

export function useBackend(): Backend {
  const [connected, setConnected] = useState(false);
  const [info, setInfo] = useState<Info | null>(null);
  const [state, setState] = useState<GameState | null>(null);
  const [toasts, setToasts] = useState<(Toast & { id: number })[]>([]);
  const [fakeCamera, setFakeCamera] = useState(false);
  const socket = useRef<WebSocket | null>(null);
  const nextToast = useRef(0);

  const showToast = useCallback((toast: Toast) => {
    const id = nextToast.current++;
    setToasts(current => [...current, { ...toast, id }]);
    window.setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), TOAST_MS);
  }, []);

  useEffect(() => {
    let stopped = false;
    let retry: number | undefined;
    function connect() {
      const ws = new WebSocket(backendUrl());
      socket.current = ws;
      // A socket that was replaced or closed by the cleanup (React StrictMode mounts twice) is ignored.
      ws.onopen = () => {
        if (socket.current !== ws) return;
        setConnected(true);
        // The fake routes only exist with fake modules; a 404 means everything is real.
        fetch(apiUrl('/api/fake'))
          .then(response => response.ok ? response.json() : { modules: [] })
          .then((body: { modules: string[] }) => { if (socket.current === ws) setFakeCamera(body.modules.includes('camera')); })
          .catch(() => {});
      };
      ws.onmessage = event => {
        if (socket.current !== ws) return;
        const message = JSON.parse(event.data) as Info | GameState | Toast;
        if (message.type === 'info') setInfo(message);
        else if (message.type === 'state') setState(message);
        else if (message.type === 'toast') showToast(message);
      };
      ws.onclose = () => {
        if (socket.current !== ws) return;
        setConnected(false);
        if (!stopped) retry = window.setTimeout(connect, RECONNECT_MS);
      };
    }
    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retry);
      const ws = socket.current;
      socket.current = null;
      ws?.close();
    };
  }, [showToast]);

  const send = useCallback((command: Command) => {
    if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify(command));
    else showToast({ type: 'toast', level: 'error', text: 'Not connected to the board.' });
  }, [showToast]);

  const fakeBoard = useCallback((board: FakeBoard) => {
    fetch(apiUrl('/api/fake/board'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(board) })
      .then(response => response.json())
      .then((body: { ok: boolean; message?: string }) => { if (!body.ok) showToast({ type: 'toast', level: 'error', text: body.message ?? 'The fake board refused that.' }); })
      .catch(() => showToast({ type: 'toast', level: 'error', text: 'Not connected to the board.' }));
  }, [showToast]);

  return { connected, info, state, toasts, send, fakeCamera, fakeBoard };
}
