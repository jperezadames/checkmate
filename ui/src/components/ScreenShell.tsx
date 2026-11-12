import type { ReactNode } from 'react';
import NavigationHint from './NavigationHint';
import { FlipDisplayButton } from './TouchscreenPreview';

export default function ScreenShell({ children }: { children: ReactNode }) {
  return (
    <div className="screen-shell">
      <header className="screen-header">
        <div className="brand">
          <img className="brand-mark" src="/favicon.svg" alt="" />
          <span className="brand-name">Check<span>Mate</span></span>
        </div>
        <div className="screen-header-actions"><span className="header-label">THE SMART CHESSBOARD</span><FlipDisplayButton /></div>
      </header>
      <main className="screen-content">{children}</main>
      <footer className="screen-footer">
        <NavigationHint />
        <span className="footer-mark" aria-hidden="true"><i /><i /><i /></span>
      </footer>
    </div>
  );
}
