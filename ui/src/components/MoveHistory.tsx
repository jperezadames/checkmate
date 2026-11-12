import { useEffect, useRef, useState, type KeyboardEvent } from 'react';

export default function MoveHistory({ moves }: { moves: string[] }) {
  const list = useRef<HTMLDivElement>(null);
  const [browsing, setBrowsing] = useState(false);
  const [focused, setFocused] = useState(false);
  useEffect(() => { if (!browsing && list.current) list.current.scrollTop = list.current.scrollHeight; }, [moves, browsing]);
  function handleKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Enter') {
      event.preventDefault(); event.stopPropagation();
      if (!event.repeat) setBrowsing(value => !value);
    } else if (browsing && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
      event.preventDefault(); event.stopPropagation();
      list.current?.scrollBy({ top: event.key === 'ArrowRight' ? 56 : -56, behavior: 'instant' });
    }
  }
  return <section className="move-history" aria-label="Move history">
    <div className="history-heading"><h2>Moves</h2><span>{browsing ? 'Turn to scroll · Select to finish' : focused ? 'Select to browse' : 'White / Black'}</span></div>
    <div className={`move-scroll${browsing ? ' browsing-moves' : ''}`} ref={list} tabIndex={0} role="region" aria-label={browsing ? 'Browsing moves. Turn to scroll. Select finishes browsing.' : 'Move history. Select to browse.'} onKeyDown={handleKey} onFocus={() => setFocused(true)} onBlur={() => { setBrowsing(false); setFocused(false); }}>
      {moves.length === 0 ? <p className="empty-moves">No moves yet</p> : <table><thead className="sr-only"><tr><th>Move</th><th>White</th><th>Black</th></tr></thead><tbody>
        {Array.from({ length: Math.ceil(moves.length / 2) }, (_, i) => <tr key={i} className={i === Math.ceil(moves.length / 2) - 1 ? 'latest-row' : ''}><th scope="row">{i + 1}.</th><td>{moves[i * 2]}</td><td>{moves[i * 2 + 1] ?? '…'}</td></tr>)}
      </tbody></table>}
    </div>
  </section>;
}
