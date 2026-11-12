import { useState } from 'react';
import Button from './components/Button';
import ScreenShell from './components/ScreenShell';
import Toasts from './components/Toasts';
import TouchscreenPreview from './components/TouchscreenPreview';
import TrainingDialog from './components/TrainingDialog';
import MainMenu from './screens/MainMenu';
import GameSetup from './screens/GameSetup';
import GameScreen from './screens/GameScreen';
import PreviewApp from './PreviewApp';
import { backendUrl, useBackend } from './backend';
import DirectionalNavigation from './components/DirectionalNavigation';

const MOCK = new URLSearchParams(window.location.search).has('mock');
const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

export default function App() {
  return MOCK ? <PreviewApp /> : <LiveApp />;
}

/** Shows the backend's newest state (§5.3) and sends commands (§5.5). The game itself lives in the backend. */
function LiveApp() {
  const { connected, info, state, toasts, send, fakeCamera, fakeBoard } = useBackend();
  const [screen, setScreen] = useState<'menu' | 'setup'>('menu');
  const [trainingDialog, setTrainingDialog] = useState(false);
  // Every phase but idle is shown on the game screen, also after a reload in the middle of a game.
  const game = state && state.phase !== 'idle' ? state : null;
  const uncalibrated = state?.phase === 'idle' && state.devices.camera === 'error';
  // With the fake camera (§5.7) the moves are clicked on the screen's board instead of made on a real one.
  const engineMove = game?.phase === 'engine_move_pending' ? game.engine_move : null;
  const boardMoves = fakeCamera && (game?.phase === 'human_turn' || engineMove);
  const fakeControls = fakeCamera ? <div className="preview-controls">
    <Button onClick={() => fakeBoard({ fen: START_FEN })}>Start position</Button>
    {engineMove && <Button onClick={() => fakeBoard({ move: engineMove.move })}>Play the computer’s move</Button>}
    <span>Fake camera · click a piece on the board, then its square</span>
  </div> : undefined;

  function leave(next: 'menu' | 'setup') {
    send({ type: 'cancel' });
    setScreen(next);
  }

  return (
    <TouchscreenPreview
      screenName={game ? 'Play vs Bot' : screen === 'menu' ? 'Main menu' : 'Play vs Bot setup'}
      caption={connected ? `Live · ${backendUrl()}` : `Connecting to ${backendUrl()}…`}
      controls={fakeControls}
    >
      <DirectionalNavigation focusKey={`${game ? "game" : screen}:${game?.phase ?? "idle"}`}>
      {game && <GameScreen
        state={game}
        connected={connected}
        sample={false}
        onLeave={() => leave('menu')}
        onNewGame={() => leave('setup')}
        onResign={() => send({ type: 'resign' })}
        onPromote={piece => send({ type: 'promote', piece })}
        onRetry={() => send({ type: 'retry' })}
        onHint={() => send({ type: 'hint' })}
        onCalibrate={() => send({ type: 'calibrate' })}
        onBoardMove={boardMoves ? move => fakeBoard({ move }) : undefined}
      />}
      {!game && screen === 'menu' && <ScreenShell><MainMenu onSelectMode={mode => mode === 'play' ? setScreen('setup') : setTrainingDialog(true)} /></ScreenShell>}
      {!game && screen === 'setup' && <GameSetup
        sample={false}
        eloRange={info ? [info.elo_min, info.elo_max] : undefined}
        disabled={!connected || state?.phase !== 'idle'}
        notice={!connected ? 'Connecting to the board…' : uncalibrated ? state.message : null}
        onCalibrate={uncalibrated ? () => send({ type: 'calibrate' }) : undefined}
        onBack={() => setScreen('menu')}
        onStart={config => send({ type: 'start_game', human_color: config.humanColor, elo: config.elo, mode: 'play' })}
      />}
      <Toasts toasts={toasts} />
      {trainingDialog && <TrainingDialog onClose={() => setTrainingDialog(false)} />}
      </DirectionalNavigation>
    </TouchscreenPreview>
  );
}
