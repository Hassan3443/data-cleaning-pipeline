// Compares docs/clean.js with the Python pipeline's output (tests/fixtures/pairs.json).
const test = require('node:test');
const assert = require('node:assert');
const C = require('../../docs/clean.js');
const pairs = require('../fixtures/pairs.json');

test('prices match the pipeline for every distinct raw value', () => {
  for (const [raw, want] of pairs.price) assert.strictEqual(C.cleanPrice(raw), want, raw);
});
test('categories match the pipeline for every distinct raw value', () => {
  for (const [raw, want] of pairs.text) assert.strictEqual(C.cleanText(raw), want, raw);
});
test('dates match the pipeline for every distinct raw value', () => {
  for (const [raw, want] of pairs.date) assert.strictEqual(C.cleanDate(raw), want, raw);
});
test('slash dates are day-first by default and month-first when asked', () => {
  assert.strictEqual(C.cleanDate('03/07/2025'), '2025-07-03');
  assert.strictEqual(C.cleanDate('03/07/2025', false), '2025-03-07');
  assert.strictEqual(C.cleanDate('03-07-2025'), '2025-03-07');
  assert.strictEqual(C.cleanDate('31/02/2025'), null);
});
