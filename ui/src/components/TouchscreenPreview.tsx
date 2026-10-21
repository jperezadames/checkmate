import { useState, type ReactNode } from 'react';
import { Maximize2 } from 'lucide-react';
import Button from './Button';

export default function TouchscreenPreview({ children, screenName = 'Main menu', controls }: { children: ReactNode; screenName?: string; controls?: ReactNode }) {
  const [framed, setFramed] = useState(() => {
    const preview = new URLSearchParams(window.location.search).get('preview');
    return preview === '1' || (import.meta.env.DEV && preview !== '0');
  });

  if (!framed) return <div className="app-viewport">{children}</div>;

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
      <div className="preview-frame">{children}</div>
      <p className="preview-caption">UI preview · Game positions and scores are illustrative. Hardware is not connected.</p>
    </div>
  );
}
