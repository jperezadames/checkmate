import { useLayoutEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Bot } from 'lucide-react';
import Button from '../components/Button';
import NavigationHint from '../components/NavigationHint';
import { FlipDisplayButton } from '../components/TouchscreenPreview';
import type { GameConfig } from '../types/game';
import './GameScreen.css';

const PRESETS = [{ name: 'Beginner', elo: 1320 }, { name: 'Casual', elo: 1500 }, { name: 'Club', elo: 1800 }, { name: 'Strong', elo: 2200 }, { name: 'Max', elo: 3190 }];

/** Keep the end presets at the installed engine's supported limits. */
function presets([min, max]: [number, number]) {
  const list = PRESETS.map((preset, i) => ({ ...preset, elo: i === 0 ? min : i === PRESETS.length - 1 ? max : preset.elo }));
  return list.filter((preset, i) => preset.elo >= min && preset.elo <= max && (i === 0 || preset.elo > list[i - 1].elo));
}

type Props = { onBack: () => void; onStart: (config: GameConfig) => void; sample?: boolean; eloRange?: [number, number]; disabled?: boolean; notice?: string | null; onCalibrate?: () => void };

export default function GameSetup({ onBack, onStart, sample = true, eloRange = [1320, 3190], disabled = false, notice, onCalibrate }: Props) {
  const [step, setStep] = useState<'color' | 'difficulty'>('color');
  const [color, setColor] = useState<GameConfig['humanColor']>('white');
  const [selectedElo, setElo] = useState(1500);
  const options = presets(eloRange);
  const elo = options.some(option => option.elo === selectedElo) ? selectedElo : options[0].elo;
  const root = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    root.current?.querySelector<HTMLElement>('[data-nav-initial]')?.focus({ preventScroll: true });
  }, [step]);

  return <main className="game-setup setup-wizard" ref={root}>
    <header><span className="setup-step">PLAY VS BOT · STEP {step === 'color' ? '1' : '2'} OF 2</span><div className="screen-header-actions">{sample && <span className="sample-label">SAMPLE GAME</span>}<FlipDisplayButton /></div></header>
    <div className="setup-title"><Bot size={30} aria-hidden="true" /><div><h1>{step === 'color' ? 'Choose your color' : 'Choose your difficulty'}</h1><p>{step === 'color' ? 'Turn the dial to browse. Select your side to continue.' : `Playing as ${color === 'random' ? 'a random color' : color}. Select a level, then start.`}</p></div></div>
    {step === 'color' ? <fieldset key="color"><legend>Your side</legend><div className="color-options">{(['white', 'random', 'black'] as const).map(c => <button key={c} type="button" aria-pressed={color === c} data-nav-initial={color === c ? '' : undefined} onClick={() => { setColor(c); setStep('difficulty'); }}><span aria-hidden="true">{c === 'white' ? '♔' : c === 'black' ? '♚' : '⇄'}</span>{c[0].toUpperCase() + c.slice(1)}<small>{c === 'white' ? 'Move first' : c === 'black' ? 'Bot moves first' : 'Let the game choose'}</small></button>)}</div></fieldset>
      : <fieldset key="difficulty"><legend>Bot strength <span>{elo} Elo selected</span></legend><div className="difficulty-options">{options.map(d => <button type="button" key={d.elo} aria-pressed={elo === d.elo} data-nav-initial={elo === d.elo ? '' : undefined} onClick={() => setElo(d.elo)}>{d.name}<strong>{d.elo}</strong><small>Elo</small></button>)}</div></fieldset>}
    <div className="setup-notice" role="status">{notice ?? (step === 'color' ? 'Next: choose your opponent’s strength.' : sample ? 'Open a sample game to explore the screen.' : 'Start the game, then set up the physical pieces.')}</div>
    <footer><NavigationHint /><div className="setup-actions"><Button onClick={() => step === 'color' ? onBack() : setStep('color')}><ArrowLeft size={18} aria-hidden="true" />{step === 'color' ? 'Menu' : 'Back to color'}</Button>{step === 'difficulty' && <>{onCalibrate && <Button disabled={disabled} onClick={onCalibrate}>Calibrate camera</Button>}<Button className="primary-action" disabled={disabled} onClick={() => onStart({ humanColor: color, elo })}>{sample ? 'Open game preview' : 'Start game'}<ArrowRight size={18} aria-hidden="true" /></Button></>}</div></footer>
  </main>;
}
