import { Bot, GraduationCap, Puzzle } from 'lucide-react';
import ModeButton from '../components/ModeButton';
import './MainMenu.css';

export type MenuMode = 'play' | 'practice';

export default function MainMenu({ onSelectMode }: { onSelectMode: (mode: MenuMode) => void }) {
  return (
    <>
      <div className="menu-heading"><h1>Make your next move.</h1><p>Choose how you want to play.</p></div>
      <nav className="mode-list" aria-label="Game modes">
        <ModeButton title="Play vs Bot" description="A worthy opponent. At your level." icon={Bot} onClick={() => onSelectMode('play')} />
        <ModeButton title="Training" description="Play, ask questions, and learn with your trainer." icon={GraduationCap} tone="gold" onClick={() => onSelectMode('practice')} />
        <ModeButton title="Puzzles" description="A little challenge. A sharper mind." icon={Puzzle} disabled />
      </nav>
    </>
  );
}
