import assert from 'node:assert/strict';
import test from 'node:test';
import { findNextTarget } from '../src/navigation/spatial.ts';

const rect = (left: number, top: number, width = 100, height = 40) => ({ left, top, right: left + width, bottom: top + height });

test('a stacked menu moves vertically and stops at its edges', () => {
  assert.equal(findNextTarget(rect(0, 0), [rect(0, 60)], 'down'), 0);
  assert.equal(findNextTarget(rect(0, 60), [rect(0, 0)], 'up'), 0);
  assert.equal(findNextTarget(rect(0, 0), [rect(0, 60)], 'up'), null);
  assert.equal(findNextTarget(rect(0, 60), [rect(0, 0)], 'down'), null);
});

test('horizontal arrows do not jump to a different full-width menu row', () => {
  for (const direction of ['left', 'right'] as const) {
    assert.equal(findNextTarget(rect(0, 0, 700), [rect(0, 60, 700)], direction), null);
  }
});

test('horizontal navigation prioritizes another option on the same row', () => {
  assert.equal(findNextTarget(rect(0, 0), [rect(60, 60), rect(240, 0)], 'right'), 1);
  assert.equal(findNextTarget(rect(240, 0), [rect(140, 70), rect(0, 0)], 'left'), 1);
});

test('vertical navigation keeps the current column where possible', () => {
  assert.equal(findNextTarget(rect(120, 0), [rect(0, 55), rect(120, 80)], 'down'), 1);
  assert.equal(findNextTarget(rect(120, 100), [rect(240, 50), rect(120, 0)], 'up'), 1);
});

test('different-size controls choose the closest aligned option', () => {
  assert.equal(findNextTarget(rect(0, 0, 600), [rect(0, 80), rect(200, 80), rect(400, 80)], 'down'), 1);
});

test('navigation can reach a back button across a gap without a shared column', () => {
  assert.equal(findNextTarget(rect(500, 300), [rect(0, 0)], 'left'), 0);
});

test('ties are deterministic and retain document order', () => {
  assert.equal(findNextTarget(rect(100, 0), [rect(0, 80), rect(200, 80)], 'down'), 0);
});

test('there is no target when the active control is the only option', () => {
  assert.equal(findNextTarget(rect(0, 0), [], 'right'), null);
});
