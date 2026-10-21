import { useState } from 'react';
import { ArrowLeft, Settings, X } from 'lucide-react';
import ChessBoard from '../components/ChessBoard';
import EvaluationBar from '../components/EvaluationBar';
import MoveHistory from '../components/MoveHistory';
import MoveFeedback from '../components/MoveFeedback';
import GameStatus from '../components/GameStatus';
import PromotionPicker from '../components/PromotionPicker';
import Modal from '../components/Modal';
import Button from '../components/Button';
import type { GameState, PieceChoice } from '../types/game';
import './GameScreen.css';

type Props = { state: GameState; connected: boolean; onLeave: () => void; onNewGame: () => void; onResign: () => void; onPromote: (piece: PieceChoice) => void; onRetry: () => void };

export default function GameScreen({ state, connected, onLeave, onNewGame, onResign, onPromote, onRetry }: Props) {
  const [settings, setSettings] = useState(false);
  const [confirm, setConfirm] = useState<'leave' | 'resign' | null>(null);
  const [showEvaluation, setShowEvaluation] = useState(true);
  const [showFeedback, setShowFeedback] = useState(true);
  const [flipped, setFlipped] = useState(false);
  const humanColor = state.human_color ?? 'white';
  const orientation = flipped ? (humanColor === 'white' ? 'black' : 'white') : humanColor;
  const pending = state.phase === 'engine_move_pending' ? state.engine_move : null;
  const pendingSquares = pending ? [pending.from, pending.to, pending.rook_from, pending.rook_to].filter((s): s is string => !!s) : [];
  const evaluation = state.evaluation?.fen === state.fen ? state.evaluation : null;
  const canResign = connected && ['human_turn', 'engine_thinking', 'engine_move_pending'].includes(state.phase);
  const botColor = humanColor === 'white' ? 'Black' : 'White';
  const player = (color: 'white' | 'black') => <><span>{color === humanColor ? 'You' : 'Stockfish'}{state.turn === color && state.phase !== 'game_over' && connected && <span className="player-turn-dot" aria-label="Side to move" />}</span><span>{color !== humanColor ? `${state.elo} Elo · ` : ''}{color[0].toUpperCase() + color.slice(1)}</span></>;

  return <main className="game-screen">
    <header className="game-header">
      <div className="game-heading"><button className="icon-button" type="button" aria-label="Leave game" onClick={() => setConfirm('leave')}><ArrowLeft size={20} aria-hidden="true" /></button><span className="game-wordmark">CheckMate</span><span className="game-mode-name">/ Play vs Bot</span></div>
      <div className="game-header-actions"><span className="sample-label">SAMPLE GAME</span><button className="icon-button" type="button" aria-label="Game settings" onClick={() => setSettings(true)}><Settings size={20} aria-hidden="true" /></button></div>
    </header>
    <div className="game-grid">
      <section className="board-column" aria-label="Current position">
        <div className="player-label">{player(orientation === 'white' ? 'black' : 'white')}</div>
        <div className={`board-and-evaluation${!showEvaluation ? ' no-evaluation' : ''}`}>
          {showEvaluation && <EvaluationBar evaluation={evaluation} flipped={orientation === 'black'} />}
          <ChessBoard fen={state.fen} orientation={orientation} lastMove={state.last_move} pendingSquares={pendingSquares} problemSquares={state.board_problem?.squares ?? []} checkedColor={state.in_check ? state.turn : null} />
        </div>
        <div className="player-label player-label-bottom">{player(orientation)}</div>
      </section>
      <aside className="game-sidebar">
        <GameStatus state={state} connected={connected} />
        {state.phase === 'promotion_choice' && state.promotion && <PromotionPicker pieces={state.promotion.choices} color={humanColor} onChoose={onPromote} disabled={!connected} />}
        {showFeedback && !['promotion_choice', 'setup_check', 'error', 'game_over'].includes(state.phase) && <MoveFeedback state={state} />}
        {!['promotion_choice', 'setup_check', 'error'].includes(state.phase) && <MoveHistory moves={state.moves_san} />}
        {state.phase === 'setup_check' && <div className="setup-instruction">White pieces on ranks 1–2.<br />Black pieces on ranks 7–8.<br /><span>Waiting for the camera to verify your board.</span></div>}
        {state.phase === 'error' && <Button disabled={!connected} onClick={onRetry}>Try again</Button>}
        {state.phase === 'game_over' && <div className="game-end-actions"><Button className="primary-action" onClick={onNewGame}>Play again</Button><Button onClick={onLeave}>Main menu</Button></div>}
        <p className="game-footnote">{connected ? 'Play on your physical board.' : 'Live updates unavailable.'}</p>
      </aside>
    </div>
    {settings && <Modal title="Game settings" onClose={() => setSettings(false)}>
      <button type="button" className="icon-button dialog-close" aria-label="Close settings" onClick={() => setSettings(false)}><X size={20} aria-hidden="true" /></button>
      <p className="settings-summary">You: {humanColor} · Bot: {botColor.toLowerCase()} · {state.elo} Elo</p>
      <label className="setting-toggle"><span>Evaluation bar</span><input type="checkbox" checked={showEvaluation} onChange={e => setShowEvaluation(e.target.checked)} /></label>
      <label className="setting-toggle"><span>Move feedback</span><input type="checkbox" checked={showFeedback} onChange={e => setShowFeedback(e.target.checked)} /></label>
      <label className="setting-toggle"><span>Flip board</span><input type="checkbox" checked={flipped} onChange={e => setFlipped(e.target.checked)} /></label>
      <div className="settings-game-actions"><Button className="danger-action" disabled={!canResign} onClick={() => { setSettings(false); setConfirm('resign'); }}>Resign</Button><Button onClick={() => { setSettings(false); setConfirm('leave'); }}>Leave game</Button></div>
    </Modal>}
    {confirm && <Modal title={confirm === 'resign' ? 'Resign this game?' : 'Leave this game?'} onClose={() => setConfirm(null)}>
      <p>{confirm === 'resign' ? 'The bot will win by resignation.' : 'This game will end and you’ll return to the main menu.'}</p>
      <div className="confirmation-actions"><Button onClick={() => setConfirm(null)}>Keep playing</Button><Button className="danger-action" onClick={() => { const action = confirm; setConfirm(null); if (action === 'resign') onResign(); else onLeave(); }}>{confirm === 'resign' ? 'Resign game' : 'Leave game'}</Button></div>
    </Modal>}
  </main>;
}
