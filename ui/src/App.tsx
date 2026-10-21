import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import Button from './components/Button';
import Modal from './components/Modal';
import ScreenShell from './components/ScreenShell';
import TouchscreenPreview from './components/TouchscreenPreview';
import MainMenu from './screens/MainMenu';
import GameSetup from './screens/GameSetup';
import GameScreen from './screens/GameScreen';
import { createGameState, previewPromotion, SCENARIOS, type Scenario } from './mocks/gameStates';
import type { GameConfig, GameState, PreviewConfig } from './types/game';

export default function App() {
  const [screen, setScreen] = useState<'menu' | 'setup' | 'game'>('menu');
  const [trainingDialog, setTrainingDialog] = useState(false);
  const [config, setConfig] = useState<PreviewConfig>({ humanColor: 'white', elo: 1500 });
  const [scenario, setScenario] = useState<Scenario>('human_turn');
  const [state, setState] = useState<GameState>(() => createGameState('human_turn', config));

  function startPreview(selection: GameConfig) {
    const resolved: PreviewConfig = {
      humanColor: selection.humanColor === 'random' ? (Math.random() < .5 ? 'white' : 'black') : selection.humanColor,
      elo: selection.elo,
    };
    setConfig(resolved);
    setScenario('human_turn');
    setState(createGameState('human_turn', resolved));
    setScreen('game');
  }

  function chooseScenario(value: Scenario) {
    setScenario(value);
    setState(createGameState(value, config));
  }

  const controls = screen === 'game' ? (
    <div className="preview-controls">
      <label htmlFor="preview-state">Preview state</label>
      <select id="preview-state" value={scenario} onChange={event => chooseScenario(event.target.value as Scenario)}>
        {SCENARIOS.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select>
      <span>Sample data · Does not control hardware</span>
    </div>
  ) : undefined;

  return <>
    <TouchscreenPreview screenName={screen === 'menu' ? 'Main menu' : screen === 'setup' ? 'Play vs Bot setup' : 'Play vs Bot'} controls={controls}>
      {screen === 'menu' && <ScreenShell><MainMenu onSelectMode={mode => mode === 'play' ? setScreen('setup') : setTrainingDialog(true)} /></ScreenShell>}
      {screen === 'setup' && <GameSetup onBack={() => setScreen('menu')} onStart={startPreview} />}
      {screen === 'game' && <GameScreen
        state={state}
        connected={scenario !== 'disconnected'}
        onLeave={() => setScreen('menu')}
        onNewGame={() => setScreen('setup')}
        onRetry={() => chooseScenario('human_turn')}
        onPromote={piece => {
          setState(current => previewPromotion(current, piece));
          setScenario('engine_thinking');
        }}
        onResign={() => {
          setState(current => ({ ...current, phase: 'game_over', result: current.human_color === 'white' ? '0-1' : '1-0', termination: 'RESIGNATION', in_check: false, engine_move: null, promotion: null, message: 'The bot wins by resignation.' }));
          setScenario('game_over');
        }}
      />}
    </TouchscreenPreview>
    {trainingDialog && <Modal title="Training" onClose={() => setTrainingDialog(false)}>
      <p>Your place to play, get feedback, and ask a chess trainer questions about the game. Training screens are coming next.</p>
      <Button onClick={() => setTrainingDialog(false)}><ArrowLeft size={18} aria-hidden="true" />Back to menu</Button>
    </Modal>}
  </>;
}
