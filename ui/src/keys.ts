import { useEffect } from 'react';

const FOCUSABLE = 'button:not(:disabled), input:not(:disabled)';

/** The 4 console buttons arrive as the keys ← → Enter Esc (§5, pi-setup.txt). ← → move the focus
 *  through the buttons of the open dialog or the screen, Enter activates the focused one, Esc closes
 *  the dialog or presses the screen's `data-back` button. With nothing focused, the first key
 *  focuses the screen's `data-autofocus` button (or its first one). */
export function useKeyNavigation() {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const root = document.querySelector<HTMLElement>('dialog[open]') ?? document.querySelector<HTMLElement>('.preview-frame, .app-viewport');
      if (!root) return;
      const items = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(item => item.getClientRects().length > 0);
      const active = document.activeElement;
      const current = active instanceof HTMLElement && items.includes(active) ? active : null;
      const start = () => items.find(item => item.closest('[data-autofocus]')) ?? items[0];

      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        if (current instanceof HTMLInputElement && current.type === 'range') return; // a slider takes the arrows itself
        event.preventDefault();
        const step = event.key === 'ArrowRight' ? 1 : items.length - 1;
        (current ? items[(items.indexOf(current) + step) % items.length] : start())?.focus();
      } else if (event.key === 'Enter') {
        if (!current) {
          event.preventDefault();
          start()?.focus();
        } else if (current instanceof HTMLInputElement && current.type === 'checkbox') {
          event.preventDefault();
          current.click();
        } // a focused button clicks itself
      } else if (event.key === 'Escape' && root.tagName !== 'DIALOG') { // a dialog closes itself
        // Without preventDefault, a dialog that the back button opens takes this Esc and closes at once.
        event.preventDefault();
        root.querySelector<HTMLElement>('[data-back]')?.click();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
}
