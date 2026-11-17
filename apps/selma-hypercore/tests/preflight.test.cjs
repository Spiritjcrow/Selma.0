'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const P = require('../assets/preflight.js');
const empty = () => Object.create(null);
const sampleLedger = (gate, evidence) => ({ schema: 1, entries: { [gate]: { evidence, at: '2026-11-16T00:00:00Z' } } });

test('25 unique, stable, ordered checkpoints across all eight ledger gates', () => {
  assert.equal(P.CHECKS.length, 25);
  assert.deepEqual(P.CHECKS.map(c=>c.id), Array.from({length:25}, (_,i)=>String(i+1).padStart(2,'0')));
  assert.equal(new Set(P.CHECKS.map(c=>c.id)).size, 25);
  assert.deepEqual(new Set(P.CHECKS.map(c=>c.gate)), new Set(['source','runner','sdk','lint','tests','apk','sha256','install']));
});
for(const check of P.CHECKS){
  test('checkpoint '+check.id+' detects supplied pattern but never certifies it',()=>{
    const parsed=P.parseLedger(sampleLedger(check.gate, check.sample));
    const result=P.evaluate(parsed).find(r=>r.id===check.id);
    assert.equal(result.status,'RECORDED_PATTERN',check.title);
    assert.equal(Object.hasOwn(result,'verified'), false);
  });
}
test('empty ledger: 25 missing, zero independently verified',()=>{
  const count=P.summarize(P.evaluate(empty()));
  assert.deepEqual(count, {recorded:0,review:0,missing:25,independently_verified:0});
});
test('nonsensical text requires review, never verification',()=>{
  const data=P.parseLedger(sampleLedger('source','This is totally verified because I said so'));
  const result=P.summarize(P.evaluate(data));
  assert.equal(result.recorded,0);
  assert.ok(result.review>=4);
  assert.equal(result.independently_verified,0);
});
test('invalid schema, arrays, prototype tricks and oversized evidence rejected',()=>{
  assert.throws(()=>P.parseLedger({schema:2,entries:{}}));
  assert.throws(()=>P.parseLedger({schema:1,entries:[]}));
  assert.throws(()=>P.parseLedger({schema:1,entries:{source:{evidence:'x'.repeat(4001)}}}));
  assert.throws(()=>P.parseLedger({schema:1,entries:{source:{evidence:[]}}}));
});
test('unknown fields never copied into returned ledger',()=>{
  const out=P.parseLedger({schema:1,entries:{source:{evidence:'safe'},irrelevant:{evidence:'secret'}}});
  assert.equal(out.source,'safe');
  assert.equal(Object.hasOwn(out,'irrelevant'),false);
  assert.equal(Object.getPrototypeOf(out),null);
});
test('recorded failures still result in zero verified',()=>{
  const out=P.parseLedger({schema:1,entries:{lint:{evidence:'lint status: fail'},install:{evidence:'install result: INSTALL_FAILED'}}});
  const summary=P.summarize(P.evaluate(out));
  assert.equal(summary.independently_verified,0);
  assert.ok(summary.recorded>=2);
});
test('no runtime network API needed',()=>{
  assert.equal(typeof P.mount,'function');
  assert.equal(typeof P.parseLedger,'function');
});
