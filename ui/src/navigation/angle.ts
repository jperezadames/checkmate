/** A bounded analog knob spans all controls. Hysteresis keeps ADC noise at a
 * boundary from moving the highlight back and forth. */
export function angleIndex(position: number, count: number, current: number): number {
  if (count === 0) return -1;
  const angle = Math.max(0, Math.min(1, position));
  const next = Math.min(count - 1, Math.floor(angle * count));
  if (current >= 0 && current < count && Math.abs(next - current) === 1) {
    const boundary = Math.max(next, current) / count;
    if (Math.abs(angle - boundary) < 0.012) return current;
  }
  return next;
}
