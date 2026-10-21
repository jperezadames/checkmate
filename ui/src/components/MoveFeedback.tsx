import type { GameState, MoveRating } from '../types/game';
import { evaluationDescription, evaluationLabel } from './EvaluationBar';

const labels: Record<MoveRating, string> = { best: 'Best move', good: 'Good move', inaccuracy: 'Inaccuracy', mistake: 'Mistake', blunder: 'Blunder' };

export default function MoveFeedback({ state }: { state: GameState }) {
  const rating = state.rating?.played === state.last_move ? state.rating : null;
  const evaluation = state.evaluation?.fen === state.fen ? state.evaluation : null;
  const mover = state.moves_san.length % 2 ? 'white' : 'black';
  return <section className="move-feedback" aria-label="Latest move analysis">
    <div className="small-label">{state.moves_san.length ? `${mover === state.human_color ? 'YOUR' : 'BOT’S'} LAST MOVE` : 'MOVE FEEDBACK'}</div>
    <div className="feedback-line"><strong>{rating?.played_san ?? state.moves_san.at(-1) ?? '—'}</strong>{rating && <span className={`rating-label rating-${rating.rating}`}>{rating.rating === 'best' || rating.rating === 'good' ? '✓ ' : '! '}{labels[rating.rating]}</span>}</div>
    <p>{evaluation ? `${evaluationLabel(evaluation)} · ${evaluationDescription(evaluation)}` : state.moves_san.length ? 'Analysis unavailable' : 'Feedback appears after a move.'}</p>
  </section>;
}
