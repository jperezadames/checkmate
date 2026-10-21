import { useState } from 'react';
import { ArrowLeft, ArrowRight, Bot } from 'lucide-react';
import Button from '../components/Button';
import type { GameConfig } from '../types/game';
import './GameScreen.css';

export default function GameSetup({ onBack, onStart }: { onBack: () => void; onStart: (config: GameConfig) => void }) {
  const [color, setColor] = useState<GameConfig['humanColor']>('white');
  const [elo, setElo] = useState(1500);
  return <main className="game-setup">
    <header><Button onClick={onBack}><ArrowLeft size={18} aria-hidden="true" />Menu</Button><span className="sample-label">SAMPLE GAME</span></header>
    <div className="setup-title"><Bot size={27} aria-hidden="true" /><div><h1>Play vs Bot</h1><p>Pick your side. Find your challenge.</p></div></div>
    <fieldset><legend>Play as</legend><div className="color-options">{(['white', 'black', 'random'] as const).map(c => <button key={c} type="button" aria-pressed={color === c} onClick={() => setColor(c)}><span aria-hidden="true">{c === 'white' ? '♔' : c === 'black' ? '♚' : '⇄'}</span>{c[0].toUpperCase() + c.slice(1)}</button>)}</div></fieldset>
    <fieldset><legend>Bot difficulty <span>{elo} Elo</span></legend><div className="difficulty-options">{[{ name: 'Beginner', elo: 1320 }, { name: 'Casual', elo: 1500 }, { name: 'Club', elo: 1800 }, { name: 'Strong', elo: 2200 }, { name: 'Max', elo: 3190 }].map(d => <button type="button" key={d.elo} aria-pressed={elo === d.elo} onClick={() => setElo(d.elo)}>{d.name}<small>{d.elo}</small></button>)}</div></fieldset>
    <footer><p>Preview an example game. Live board integration comes later.</p><Button className="primary-action" onClick={() => onStart({ humanColor: color, elo })}>Open game preview<ArrowRight size={18} aria-hidden="true" /></Button></footer>
  </main>;
}
