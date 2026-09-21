const {test} = require('node:test');
const assert = require('node:assert/strict');
const {validToken, validComputer, checkPairing, newEvents} = require('../logic');
test('rejects guessed shapes, paths and overlong tokens', () => {
  assert.equal(validToken('a'.repeat(43)), true);
  assert.equal(validToken('../anything'), false);
  assert.equal(validComputer('pc/other'), false);
});
test('codes expire and cannot be used by a second identity', () => {
  const code = {computer_id:'pc', expiresAt:{toMillis:()=>100}};
  assert.equal(checkPairing(code,'one',50),null);
  assert.equal(checkPairing(code,'one',101),'failed-precondition');
  assert.equal(checkPairing({...code,usedBy:'one'},'two',50),'failed-precondition');
  assert.equal(checkPairing({...code,usedBy:'one'},'one',50),null);
});
test('progress updates do not resend notifications; parallel files retain their events', () => {
  const first={id:'1',kind:'completed'}, second={id:'2',kind:'paused'};
  assert.deepEqual(newEvents({notification_events:[first]}, {notification_events:[first,second]}),[second]);
  assert.deepEqual(newEvents({notification_events:[first]}, {notification_events:[first],progress_percent:90}),[]);
});
