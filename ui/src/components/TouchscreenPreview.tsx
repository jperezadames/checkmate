import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Maximize2, RotateCw } from 'lucide-react';
import Button from './Button';

const SAMPLE_CAPTION = 'UI preview · Game positions and scores are illustrative. Hardware is not connected.';
const DISPLAY_STORAGE_KEY = 'checkmate.display-flipped';
const DisplayOrientation = createContext<{ flipped: boolean; toggle: () => void } | null>(null);

export function FlipDisplayButton() {
  const orientation = useContext(DisplayOrientation);
  if (!orientation) return null;

  return <button type="button" className="icon-button display-flip-button" aria-label="Flip display" title="Flip display 180°" aria-pressed={orientation.flipped} onClick={orientation.toggle}>
    <RotateCw size={20} aria-hidden="true" />
  </button>;
}

export default function TouchscreenPreview({ children, screenName = 'Main menu', controls, caption = SAMPLE_CAPTION }: { children: ReactNode; screenName?: string; controls?: ReactNode; caption?: string }) {
  const [framed, setFramed] = useState(() => {
    const preview = new URLSearchParams(window.location.search).get('preview');
    return preview === '1' || (import.meta.env.DEV && preview !== '0');
  });
  const [flipped, setFlipped] = useState(() => {
    try {
      return window.localStorage.getItem(DISPLAY_STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(DISPLAY_STORAGE_KEY, String(flipped));
    } catch {
      // Rotation still works for the current page if storage is unavailable.
    }
  }, [flipped]);

  const display = <div className={framed ? 'preview-frame' : 'app-viewport'} data-display-flipped={flipped || undefined}>
    <DisplayOrientation.Provider value={{ flipped, toggle: () => setFlipped(current => !current) }}>
      {children}
    </DisplayOrientation.Provider>
  </div>;

  if (!framed) return display;

  return (
    <div className="preview-workspace">
      <div className="preview-toolbar">
        <div>
          <p className="preview-title">Touchscreen preview<span className="preview-size">800 × 480 · LANDSCAPE</span></p>
          <p className="preview-description">CheckMate / {screenName}</p>
        </div>
        <Button onClick={() => setFramed(false)}><Maximize2 size={15} aria-hidden="true" />Fill window</Button>
      </div>
      {controls}
      {display}
      <p className="preview-caption">{caption}</p>
    </div>
  );
}
