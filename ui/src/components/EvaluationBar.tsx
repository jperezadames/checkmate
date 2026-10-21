import type { Evaluation } from '../types/game';

export function evaluationLabel(evaluation: Evaluation | null): string {
  if (!evaluation) return '—';
  if (evaluation.mate_in !== null) return evaluation.mate_in === 0 ? 'Mate' : `${evaluation.mate_in < 0 ? '−' : ''}M${Math.abs(evaluation.mate_in)}`;
  if (evaluation.score_cp === null) return '—';
  const score = evaluation.score_cp / 100;
  return `${score > 0 ? '+' : score < 0 ? '−' : ''}${Math.abs(score).toFixed(2)}`;
}

export function evaluationDescription(evaluation: Evaluation | null): string {
  if (!evaluation) return 'Analysis unavailable';
  if (evaluation.mate_in !== null) return evaluation.mate_in === 0 ? 'Checkmate' : `${evaluation.mate_in > 0 ? 'White' : 'Black'} has a forced mate`;
  if (evaluation.score_cp === null) return 'Analysis unavailable';
  if (Math.abs(evaluation.score_cp) <= 15) return 'Roughly equal';
  return `${evaluation.score_cp > 0 ? 'White' : 'Black'} is ahead`;
}

export default function EvaluationBar({ evaluation, flipped }: { evaluation: Evaluation | null; flipped: boolean }) {
  // A bounded visual scale for advantage, never a probability of winning.
  const whiteShare = !evaluation ? 50 : evaluation.mate_in !== null ? (evaluation.mate_in > 0 ? 100 : evaluation.mate_in < 0 ? 0 : 50) : 50 + 45 * Math.tanh((evaluation.score_cp ?? 0) / 400);
  return <div className={`evaluation-bar${flipped ? ' evaluation-flipped' : ''}${!evaluation ? ' evaluation-unavailable' : ''}`} role="img" aria-label={`Position evaluation ${evaluationLabel(evaluation)}. ${evaluationDescription(evaluation)}. White’s perspective.`}>
    <div className="evaluation-black" style={{ flex: 100 - whiteShare }} />
    <div className="evaluation-white" style={{ flex: whiteShare }} />
    <span className="evaluation-number">{evaluationLabel(evaluation)}</span>
  </div>;
}
