import type { ReactNode } from 'react';

export default function ScreenShell({ children }: { children: ReactNode }) {
  return (
    <div className="screen-shell">
      <header className="screen-header">
        <div className="brand">
          <img className="brand-mark" src="/favicon.svg" alt="" />
          <span className="brand-name">Check<span>Mate</span></span>
        </div>
        <span className="header-label">THE SMART CHESSBOARD</span>
      </header>
      <main className="screen-content">{children}</main>
      <footer className="screen-footer">
        <span>Your board. Your next move.</span>
        <span className="footer-mark" aria-hidden="true"><i /><i /><i /></span>
      </footer>
    </div>
  );
}
