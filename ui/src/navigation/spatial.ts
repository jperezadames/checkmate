export type Direction = 'left' | 'right' | 'up' | 'down';

export interface TargetRect { left: number; right: number; top: number; bottom: number }

/** Choose by screen position. Edges stop; an aligned row/column takes priority. */
export function findNextTarget(origin: TargetRect, candidates: TargetRect[], direction: Direction): number | null {
  const horizontal = direction === 'left' || direction === 'right';
  const sign = direction === 'right' || direction === 'down' ? 1 : -1;
  const x = (origin.left + origin.right) / 2;
  const y = (origin.top + origin.bottom) / 2;
  const ranked = candidates.map((rect, index) => {
    const dx = (rect.left + rect.right) / 2 - x;
    const dy = (rect.top + rect.bottom) / 2 - y;
    const forward = (horizontal ? dx : dy) * sign;
    const perpendicular = Math.abs(horizontal ? dy : dx);
    const overlap = horizontal
      ? Math.min(origin.bottom, rect.bottom) - Math.max(origin.top, rect.top)
      : Math.min(origin.right, rect.right) - Math.max(origin.left, rect.left);
    return { index, forward, aligned: overlap > 1, distance: forward + perpendicular * 2 };
  }).filter(target => target.forward > 1);
  ranked.sort((a, b) => Number(b.aligned) - Number(a.aligned) || a.distance - b.distance || a.index - b.index);
  return ranked[0]?.index ?? null;
}
