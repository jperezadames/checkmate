import type { Toast } from '../types/game';

export default function Toasts({ toasts }: { toasts: (Toast & { id: number })[] }) {
  return <div className="toasts" role="status" aria-live="polite">{toasts.map(toast => <div key={toast.id} className={`toast toast-${toast.level}`}>{toast.text}</div>)}</div>;
}
