import assert from 'node:assert/strict';
import test from 'node:test';
import { angleIndex } from '../src/navigation/angle.ts';

test('both physical stops and every control are reachable', () => {
  for (const count of [1, 3, 7, 10]) {
    assert.equal(angleIndex(0, count, -1), 0);
    assert.equal(angleIndex(1, count, -1), count - 1);
    for (let index = 0; index < count; index++) {
      assert.equal(angleIndex((index + 0.5) / count, count, -1), index);
    }
  }
});

test('boundary noise holds focus until the knob crosses the hysteresis margin', () => {
  assert.equal(angleIndex(0.501, 4, 1), 1);
  assert.equal(angleIndex(0.499, 4, 2), 2);
  assert.equal(angleIndex(0.52, 4, 1), 2);
  assert.equal(angleIndex(0.48, 4, 2), 1);
});

test('an empty screen and a stale focus after a screen change are handled', () => {
  assert.equal(angleIndex(0.5, 0, -1), -1);
  assert.equal(angleIndex(1, 3, 8), 2);
});
