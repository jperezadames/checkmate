import { AlertTriangle, CircleCheck, LoaderCircle, WifiOff } from 'lucide-react';
import type { GameState } from '../types/game';

export default function GameStatus({ state, connected }: { state: GameState; connected: boolean }) {
  const problem = state.board_problem;
  let eyebrow = 'YOUR TURN';
  let title = 'What’s your next move?';
  let text = state.message;
  let warning = false;
  if (!connected) { eyebrow = 'CONNECTION LOST'; title = 'Reconnecting…'; text = 'Waiting for live updates. The board shows the last confirmed position.'; warning = true; }
  else if (state.phase === 'error') { eyebrow = 'DEVICE ERROR'; title = 'Check your camera'; warning = true; }
  else if (problem) { eyebrow = 'CHECK THE BOARD'; title = 'A piece is out of place'; text = `${problem.text} Check: ${problem.squares.join(', ')}.`; warning = true; }
  else if (state.phase === 'setup_check') { eyebrow = 'BOARD SETUP'; title = 'Set up your pieces'; }
  else if (state.phase === 'calibrating') { eyebrow = 'CAMERA SETUP'; title = 'Calibrating…'; }
  else if (state.phase === 'idle') { eyebrow = 'READY TO PLAY'; title = 'Choose a new game'; }
  else if (state.phase === 'engine_thinking') { eyebrow = 'BOT’S TURN'; title = 'Thinking…'; }
  else if (state.phase === 'engine_move_pending') { eyebrow = 'BOT’S TURN'; title = 'Play the bot’s move'; }
  else if (state.phase === 'promotion_choice') { eyebrow = 'YOUR TURN'; title = 'Promote your pawn'; }
  else if (state.phase === 'game_over') { eyebrow = 'GAME OVER'; title = state.result === '1/2-1/2' ? 'It’s a draw' : state.result === (state.human_color === 'white' ? '1-0' : '0-1') ? 'You win!' : 'The bot wins'; text = `${state.result ?? ''} · ${(state.termination ?? 'Game ended').toLowerCase().replaceAll('_', ' ')}`; }
  else if (state.in_check) { title = 'You’re in check'; warning = true; }
  const move = state.phase === 'engine_move_pending' && connected ? state.engine_move : null;
  return <section className={`game-status${warning ? ' status-warning' : ''}`} aria-live="polite" aria-atomic="true">
    <div className="status-eyebrow">{!connected ? <WifiOff size={13} aria-hidden="true" /> : warning ? <AlertTriangle size={13} aria-hidden="true" /> : state.phase === 'engine_thinking' ? <LoaderCircle className="thinking-spinner" size={14} aria-hidden="true" /> : state.phase === 'game_over' ? <CircleCheck size={14} aria-hidden="true" /> : <span className="status-dot" />}{eyebrow}</div>
    <h1>{title}</h1>
    {move && <div className="bot-move"><strong>{move.san}</strong><span>{move.from} → {move.to}</span></div>}
    <p>{text}</p>
    {move?.rook_from && <p className="special-move">Also move the rook: {move.rook_from} → {move.rook_to}</p>}
    {move?.capture_square && <p className="special-move">Remove the captured piece on {move.capture_square}.</p>}
    {move?.promotion && <p className="special-move">Replace the pawn with a {({ q: 'queen', r: 'rook', b: 'bishop', n: 'knight' })[move.promotion]}.</p>}
    {move && <span className="confirmation-note">Waiting for camera confirmation</span>}
  </section>;
}
