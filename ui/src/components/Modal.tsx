import { useEffect, useRef, type ReactNode } from 'react';

export default function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = 'active-modal-title';
  useEffect(() => {
    const element = dialog.current;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element?.showModal();
    return () => {
      element?.close();
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);
  return <dialog className="game-dialog" ref={dialog} aria-labelledby={titleId} onClose={() => { if (!dialog.current?.open) onClose(); }}>
    <h2 id={titleId}>{title}</h2>{children}
  </dialog>;
}
