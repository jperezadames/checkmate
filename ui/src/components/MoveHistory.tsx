import { useEffect, useRef } from 'react';

export default function MoveHistory({ moves }: { moves: string[] }) {
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => { if (list.current) list.current.scrollTop = list.current.scrollHeight; }, [moves]);
  return <section className="move-history" aria-label="Move history">
    <div className="history-heading"><h2>Moves</h2><span>White / Black</span></div>
    <div className="move-scroll" ref={list} tabIndex={0} role="region" aria-label="Scrollable move list">
      {moves.length === 0 ? <p className="empty-moves">No moves yet</p> : <table><thead className="sr-only"><tr><th>Move</th><th>White</th><th>Black</th></tr></thead><tbody>
        {Array.from({ length: Math.ceil(moves.length / 2) }, (_, i) => <tr key={i} className={i === Math.ceil(moves.length / 2) - 1 ? 'latest-row' : ''}><th scope="row">{i + 1}.</th><td>{moves[i * 2]}</td><td>{moves[i * 2 + 1] ?? '…'}</td></tr>)}
      </tbody></table>}
    </div>
  </section>;
}
