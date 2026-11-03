import { useState } from 'react';
import { ArrowLeft, ArrowRight, Bot } from 'lucide-react';
import Button from '../components/Button';
import type { GameConfig } from '../types/game';
import './GameScreen.css';

const PRESETS = [{ name: 'Beginner', elo: 1320 }, { name: 'Casual', elo: 1500 }, { name: 'Club', elo: 1800 }, { name: 'Strong', elo: 2200 }, { name: 'Max', elo: 3190 }];

/** The contract's presets (§3.2), with Beginner and Max at the engine's own limits from `info`. */
function presets([min, max]: [number, number]) {
  const list = PRESETS.map((preset, i) => ({ ...preset, elo: i === 0 ? min : i === PRESETS.length - 1 ? max : preset.elo }));
  return list.filter((preset, i) => preset.elo >= min && preset.elo <= max && (i === 0 || preset.elo > list[i - 1].elo));
}

type Props = { onBack: () => void; onStart: (config: GameConfig) => void; sample?: boolean; eloRange?: [number, number]; disabled?: boolean; notice?: string | null; onCalibrate?: () => void };

export default function GameSetup({ onBack, onStart, sample = true, eloRange = [1320, 3190], disabled = false, notice, onCalibrate }: Props) {
  const [color, setColor] = useState<GameConfig['humanColor']>('white');
  const [elo, setElo] = useState(1500);
  return <main className="game-setup">
    <header><Button onClick={onBack} data-back><ArrowLeft size={18} aria-hidden="true" />Menu</Button>{sample && <span className="sample-label">SAMPLE GAME</span>}</header>
    <div className="setup-title"><Bot size={27} aria-hidden="true" /><div><h1>Play vs Bot</h1><p>Pick your side. Find your challenge.</p></div></div>
    <fieldset><legend>Play as</legend><div className="color-options">{(['white', 'black', 'random'] as const).map(c => <button key={c} type="button" aria-pressed={color === c} data-autofocus={color === c || undefined} onClick={() => setColor(c)}><span aria-hidden="true">{c === 'white' ? '♔' : c === 'black' ? '♚' : '⇄'}</span>{c[0].toUpperCase() + c.slice(1)}</button>)}</div></fieldset>
    <fieldset><legend>Bot difficulty <span>{elo} Elo</span></legend><div className="difficulty-options">{presets(eloRange).map(d => <button type="button" key={d.elo} aria-pressed={elo === d.elo} onClick={() => setElo(d.elo)}>{d.name}<small>{d.elo}</small></button>)}</div></fieldset>
    <footer><p>{notice ?? (sample ? 'Preview an example game. Live board integration comes later.' : 'Then set up the pieces on the board.')}</p><div className="setup-actions">{onCalibrate && <Button disabled={disabled} onClick={onCalibrate}>Calibrate camera</Button>}<Button className="primary-action" disabled={disabled} onClick={() => onStart({ humanColor: color, elo })}>{sample ? 'Open game preview' : 'Start game'}<ArrowRight size={18} aria-hidden="true" /></Button></div></footer>
  </main>;
}
