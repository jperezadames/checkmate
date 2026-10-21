import type { Color, PieceChoice } from '../types/game';

const choices: Record<PieceChoice, { name: string; symbol: string }> = { q: { name: 'Queen', symbol: '♛' }, r: { name: 'Rook', symbol: '♜' }, b: { name: 'Bishop', symbol: '♝' }, n: { name: 'Knight', symbol: '♞' } };

export default function PromotionPicker({ pieces, color, onChoose, disabled }: { pieces: PieceChoice[]; color: Color; onChoose: (piece: PieceChoice) => void; disabled: boolean }) {
  return <div className="promotion-picker" role="group" aria-label="Choose promotion piece">{pieces.map(piece => <button key={piece} type="button" onClick={() => onChoose(piece)} disabled={disabled} aria-label={`Promote to ${choices[piece].name}`}><span className={`promotion-symbol ${color === 'white' ? 'white-piece' : 'black-piece'}`} aria-hidden="true">{choices[piece].symbol}</span><span>{choices[piece].name}</span></button>)}</div>;
}
