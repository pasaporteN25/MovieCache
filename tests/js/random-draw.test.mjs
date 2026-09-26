// U8.3 draw rules. Run: node --test tests/js/random-draw.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { drawRandomItem, randomResultState } from '../../src/movie_inbox/web/static/js/core/random-draw.js';

const a = { id: 'a' }, b = { id: 'b' }, c = { id: 'c' };

test('no candidates draw nothing', () => {
  assert.equal(drawRandomItem([]), null);
  assert.equal(drawRandomItem(undefined), null);
});

test('one candidate may repeat; several never repeat the result on screen', () => {
  assert.equal(drawRandomItem([a], { excludeId: 'a', random: () => 0 }), a);
  for (const r of [0, 0.5, 0.999999]) {
    assert.notEqual(drawRandomItem([a, b, c], { excludeId: 'b', random: () => r }).id, 'b');
  }
  assert.equal(drawRandomItem([a, b], { excludeId: 'a', random: () => 0.99 }), b);
});

test('state separates the work from the preference that excludes it', () => {
  assert.equal(randomResultState(a, { available: true, catalogOnly: true }), 'available');
  assert.equal(randomResultState(a, { available: false, catalogOnly: false }), 'unavailable');
  assert.equal(randomResultState(a, { available: false, catalogOnly: true }), 'out-of-scope');
  assert.equal(randomResultState(null, { available: false, catalogOnly: false }), 'error');
});
