export type Color = 'white' | 'black';
export type PieceChoice = 'q' | 'r' | 'b' | 'n';
export type Phase = 'idle' | 'calibrating' | 'setup_check' | 'human_turn' | 'engine_thinking' | 'engine_move_pending' | 'promotion_choice' | 'game_over' | 'error';
export type MoveRating = 'best' | 'good' | 'inaccuracy' | 'mistake' | 'blunder';

export interface MoveDetails {
  move: string;
  san: string;
  from: string;
  to: string;
  rook_from: string | null;
  rook_to: string | null;
  capture_square: string | null;
  promotion: PieceChoice | null;
}

export interface Rating {
  ok: true;
  played: string;
  played_san: string;
  best: string;
  best_san: string;
  score_before: number | null;
  score_after: number | null;
  mate_in: number | null;
  cp_loss: number;
  rating: MoveRating;
}

export interface Evaluation {
  fen: string;
  score_cp: number | null;
  mate_in: number | null;
}

/** Full display snapshot from contracts/interfaces.md §5.3. No local chess rules. */
export interface GameState {
  type: 'state';
  phase: Phase;
  mode: 'play' | 'practice' | null;
  fen: string | null;
  human_color: Color | null;
  turn: Color | null;
  elo: number | null;
  moves_san: string[];
  last_move: string | null;
  in_check: boolean;
  engine_move: MoveDetails | null;
  promotion: { from: string; to: string; choices: PieceChoice[] } | null;
  hint: MoveDetails | null;
  rating: Rating | null;
  evaluation: Evaluation | null;
  board_problem: { squares: string[]; text: string } | null;
  result: '1-0' | '0-1' | '1/2-1/2' | null;
  termination: string | null;
  message: string;
  devices: Record<'camera' | 'engine' | 'led', 'ok' | 'error'>;
}

export interface GameConfig { humanColor: Color | 'random'; elo: number }
export interface PreviewConfig { humanColor: Color; elo: number }
