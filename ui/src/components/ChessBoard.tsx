import type { Color } from '../types/game';

const symbols: Record<string, string> = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟' };
const names: Record<string, string> = { k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' };

/** Decode placement for display only; rules and move validation remain on the backend. */
export function readPosition(fen: string | null): Record<string, string> {
  if (!fen) return {};
  const ranks = fen.split(' ')[0].split('/');
  if (ranks.length !== 8) return {};
  const pieces: Record<string, string> = {};
  for (const [row, rank] of ranks.entries()) {
    let file = 0;
    for (const character of rank) {
      if (/^[1-8]$/.test(character)) file += Number(character);
      else if (symbols[character.toLowerCase()] && file < 8) {
        pieces[`${'abcdefgh'[file]}${8 - row}`] = character;
        file++;
      } else return {};
    }
    if (file !== 8) return {};
  }
  return pieces;
}

interface BoardProps {
  fen: string | null;
  orientation: Color;
  lastMove: string | null;
  pendingSquares: string[];
  problemSquares: string[];
  checkedColor: Color | null;
}

export default function ChessBoard({ fen, orientation, lastMove, pendingSquares, problemSquares, checkedColor }: BoardProps) {
  const position = readPosition(fen);
  const files = orientation === 'white' ? 'abcdefgh' : 'hgfedcba';
  const ranks = orientation === 'white' ? '87654321' : '12345678';
  const description = Object.entries(position).map(([square, piece]) => `${square}: ${piece === piece.toUpperCase() ? 'White' : 'Black'} ${names[piece.toLowerCase()]}`).join(', ');
  return (
    <div className="chess-board" role="img" aria-label={`Current board, ${orientation} at the bottom. ${description}`}>
      {[...ranks].flatMap((rank, row) => [...files].map((file, column) => {
        const square = file + rank;
        const piece = position[square];
        const dark = ('abcdefgh'.indexOf(file) + Number(rank)) % 2 === 1;
        const last = lastMove?.slice(0, 2) === square || lastMove?.slice(2, 4) === square;
        const checked = checkedColor && piece === (checkedColor === 'white' ? 'K' : 'k');
        return <div key={square} data-square={square} className={`chess-square${dark ? ' dark-square' : ''}${last ? ' last-square' : ''}${pendingSquares.includes(square) ? ' pending-square' : ''}${problemSquares.includes(square) ? ' problem-square' : ''}${checked ? ' checked-square' : ''}`} aria-hidden="true">
          {piece && <span className={`chess-piece ${piece === piece.toUpperCase() ? 'white-piece' : 'black-piece'}`}>{symbols[piece.toLowerCase()]}</span>}
          {column === 0 && <span className="square-coordinate rank-coordinate">{rank}</span>}
          {row === 7 && <span className="square-coordinate file-coordinate">{file}</span>}
          {problemSquares.includes(square) && <span className="problem-marker">!</span>}
        </div>;
      }))}
    </div>
  );
}
