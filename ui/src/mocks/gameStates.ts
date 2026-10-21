import type { GameState, PieceChoice, PreviewConfig, Rating } from '../types/game';

export const SCENARIOS = [
  { id: 'human_turn', label: 'Your turn' },
  { id: 'engine_thinking', label: 'Bot thinking' },
  { id: 'engine_move_pending', label: 'Play the bot’s move' },
  { id: 'check', label: 'In check' },
  { id: 'board_problem', label: 'Board mismatch' },
  { id: 'promotion_choice', label: 'Promotion' },
  { id: 'game_over', label: 'Game over' },
  { id: 'disconnected', label: 'Connection lost' },
  { id: 'setup_check', label: 'Board setup' },
  { id: 'error', label: 'Device error' },
  { id: 'analysis_unavailable', label: 'Analysis unavailable' },
  { id: 'mistake', label: 'Move rated as a mistake' },
] as const;
export type Scenario = typeof SCENARIOS[number]['id'];

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const AFTER_BC5 = 'r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4';
const AFTER_D3 = 'r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R b KQkq - 0 4';
const OPENING = ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5'];

function sampleRating(move: string, san: string): Rating {
  return { ok: true, played: move, played_san: san, best: move, best_san: san, score_before: 30, score_after: 30, mate_in: null, cp_loss: 0, rating: 'best' };
}

/** Illustrative snapshots, not a simulated engine. Scores are sample data. */
export function createGameState(scenario: Scenario, config: PreviewConfig): GameState {
  const white = config.humanColor === 'white';
  const fen = white ? AFTER_BC5 : AFTER_D3;
  const state: GameState = {
    type: 'state', phase: 'human_turn', mode: 'play', fen,
    human_color: config.humanColor, turn: config.humanColor, elo: config.elo,
    moves_san: white ? [...OPENING] : [...OPENING, 'd3'],
    last_move: white ? 'f8c5' : 'd2d3', in_check: false,
    engine_move: null, promotion: null, hint: null,
    rating: sampleRating(white ? 'f8c5' : 'd2d3', white ? 'Bc5' : 'd3'),
    evaluation: { fen, score_cp: 30, mate_in: null },
    board_problem: null, result: null, termination: null,
    message: 'Make your move on the physical board.',
    devices: { camera: 'ok', engine: 'ok', led: 'ok' },
  };
  if (scenario === 'engine_thinking' || scenario === 'engine_move_pending') {
    state.phase = scenario;
    state.fen = white ? AFTER_D3 : AFTER_BC5;
    state.turn = white ? 'black' : 'white';
    state.moves_san = white ? [...OPENING, 'd3'] : [...OPENING];
    state.last_move = white ? 'd2d3' : 'f8c5';
    state.rating = sampleRating(state.last_move, white ? 'd3' : 'Bc5');
    state.evaluation = { fen: state.fen, score_cp: 30, mate_in: null };
    if (scenario === 'engine_move_pending') {
      state.engine_move = { move: white ? 'g8f6' : 'd2d3', san: white ? 'Nf6' : 'd3', from: white ? 'g8' : 'd2', to: white ? 'f6' : 'd3', rook_from: null, rook_to: null, capture_square: null, promotion: null };
      state.message = 'Follow the highlighted squares on your physical board.';
    } else state.message = 'The computer is choosing its move.';
  }
  if (scenario === 'check') {
    state.fen = white ? '4r1k1/5ppp/8/8/8/8/5PPP/4K3 w - - 0 1' : '4k3/5ppp/8/8/8/8/5PPP/4R1K1 b - - 0 1';
    state.moves_san = []; state.last_move = null; state.in_check = true;
    state.rating = null; state.evaluation = null;
    state.message = 'Your king is in check. Make a move that protects it.';
  }
  if (scenario === 'board_problem') {
    state.board_problem = { squares: ['e2', 'e5'], text: 'Put the pieces back on e2 and e5 to match the screen.' };
  }
  if (scenario === 'promotion_choice') {
    state.phase = 'promotion_choice';
    state.fen = white ? '8/4P1k1/8/8/8/8/6K1/8 w - - 0 1' : '8/6k1/8/8/8/8/4p1K1/8 b - - 0 1';
    state.promotion = { from: white ? 'e7' : 'e2', to: white ? 'e8' : 'e1', choices: ['q', 'r', 'b', 'n'] };
    state.moves_san = white ? [] : ['Kg2']; state.last_move = white ? null : 'g1g2'; state.rating = null; state.evaluation = null;
    state.message = 'Choose a piece, then replace your pawn on the physical board.';
  }
  if (scenario === 'game_over') {
    state.phase = 'game_over';
    state.fen = 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3';
    state.turn = 'white'; state.moves_san = ['f3', 'e5', 'g4', 'Qh4#']; state.last_move = 'd8h4';
    state.result = '0-1'; state.termination = 'CHECKMATE'; state.in_check = true;
    state.rating = null; state.evaluation = null;
    state.message = 'Black wins by checkmate.';
  }
  if (scenario === 'setup_check') {
    state.phase = 'setup_check'; state.fen = START; state.turn = 'white';
    state.moves_san = []; state.last_move = null; state.rating = null; state.evaluation = null;
    state.message = 'Arrange the physical pieces to match the starting position.';
  }
  if (scenario === 'error') {
    state.phase = 'error'; state.devices.camera = 'error';
    state.message = 'The camera is unavailable. Check its connection and try again.';
  }
  if (scenario === 'analysis_unavailable') { state.rating = null; state.evaluation = null; }
  if (scenario === 'mistake') {
    state.fen = 'rnbqkbnr/pppppppp/8/8/8/5P2/PPPPP1PP/RNBQKBNR b KQkq - 0 1';
    state.turn = 'black'; state.phase = white ? 'engine_thinking' : 'human_turn';
    state.moves_san = ['f3']; state.last_move = 'f2f3';
    state.rating = { ok: true, played: 'f2f3', played_san: 'f3', best: 'g1f3', best_san: 'Nf3', score_before: 30, score_after: -145, mate_in: null, cp_loss: 175, rating: 'mistake' };
    state.evaluation = { fen: state.fen, score_cp: -145, mate_in: null };
    state.message = white ? 'The computer is choosing its move.' : 'Make your move on the physical board.';
  }
  return state;
}

export function previewPromotion(state: GameState, piece: PieceChoice): GameState {
  const white = state.human_color === 'white';
  const fen = white ? `4${piece.toUpperCase()}3/6k1/8/8/8/8/6K1/8 b - - 0 1` : `8/6k1/8/8/8/8/6K1/4${piece}3 w - - 0 2`;
  return { ...state, phase: 'engine_thinking', fen, turn: white ? 'black' : 'white', promotion: null, moves_san: [...state.moves_san, `${white ? 'e8' : 'e1'}=${piece.toUpperCase()}`], last_move: `${white ? 'e7e8' : 'e2e1'}${piece}`, message: 'Sample promotion applied. The bot is thinking.', rating: null, evaluation: null };
}
