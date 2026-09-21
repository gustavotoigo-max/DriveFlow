const {test, before, after} = require('node:test');
const fs = require('node:fs');
const {initializeTestEnvironment, assertSucceeds, assertFails} = require('@firebase/rules-unit-testing');
const {doc, collection, getDoc, getDocs, setDoc} = require('firebase/firestore');
let env;
before(async () => {
  env = await initializeTestEnvironment({projectId:'demo-driveflow',firestore:{host:'127.0.0.1',port:8085,rules:fs.readFileSync('../firestore.rules','utf8')}});
  await env.withSecurityRulesDisabled(async context => {
    const db=context.firestore();
    await setDoc(doc(db,'computers/pc'),{status:'uploading'});
    await setDoc(doc(db,'readers/owner/computers/pc'),{computer_name:'PC'});
    await setDoc(doc(db,'pairing_codes/secret'),{computer_id:'pc'});
  });
});
after(async()=>{await env?.cleanup()});
test('only paired reader can read the machine; never write or enumerate all machines', async()=>{
  const own=env.authenticatedContext('owner').firestore();
  const other=env.authenticatedContext('other').firestore();
  await assertSucceeds(getDoc(doc(own,'computers/pc')));
  await assertFails(getDoc(doc(other,'computers/pc')));
  await assertFails(getDoc(doc(env.unauthenticatedContext().firestore(),'computers/pc')));
  await assertFails(setDoc(doc(own,'computers/pc'),{status:'completed'}));
  await assertFails(getDocs(collection(own,'computers')));
  await assertSucceeds(getDocs(collection(own,'readers/owner/computers')));
  await assertFails(getDoc(doc(own,'pairing_codes/secret')));
  await assertFails(setDoc(doc(other,'readers/other/computers/pc'),{}));
});

test('pairing is atomic, single-use, expiring and revocable', async()=>{
  const handlers = require('../index');
  const {getFirestore, Timestamp} = require('firebase-admin/firestore');
  const {hash} = require('../logic');
  const admin = getFirestore();
  const token = 'b'.repeat(43);
  await admin.doc(`pairing_codes/${hash(token)}`).set({computer_id:'paired-pc',computer_name:'PC',expiresAt:Timestamp.fromMillis(Date.now()+60000)});
  const requests = ['phone1','phone2'].map(uid=>handlers.pairComputer.run({auth:{uid},data:{token,deviceName:'Test phone'}}));
  const results = await Promise.allSettled(requests);
  require('node:assert/strict').equal(results.filter(r=>r.status==='fulfilled').length,1);
  const winner = results[0].status==='fulfilled' ? 'phone1' : 'phone2';
  await handlers.unpairComputer.run({auth:{uid:winner},data:{computerId:'paired-pc'}});
  await require('node:assert/strict').rejects(handlers.pairComputer.run({auth:{uid:winner},data:{token}}));
  const expired = 'c'.repeat(43);
  await admin.doc(`pairing_codes/${hash(expired)}`).set({computer_id:'paired-pc',expiresAt:Timestamp.fromMillis(Date.now()-1000)});
  await require('node:assert/strict').rejects(handlers.pairComputer.run({auth:{uid:winner},data:{token:expired}}));
});

test('notification retry sends once and respects revocation and mute', async()=>{
  const handlers = require('../index');
  const {getFirestore} = require('firebase-admin/firestore');
  const {getMessaging} = require('firebase-admin/messaging');
  const admin = getFirestore();
  const assert = require('node:assert/strict');
  const messages=[];
  const messaging=getMessaging();
  const original=messaging.send;
  messaging.send=async msg=>{messages.push(msg);return 'fake-id'};
  try {
    for (const uid of ['active','muted','revoked']) {
      await admin.doc(`computers/notify-pc/readers/${uid}`).set({deviceName:'Test'});
      await admin.doc(`readers/${uid}`).set({token:'test-token-'+uid,notifications:uid!=='muted'});
      if(uid!=='revoked') await admin.doc(`readers/${uid}/computers/notify-pc`).set({computer_name:'PC'});
    }
    const event={params:{computerId:'notify-pc'},data:{before:{data:()=>({})},after:{exists:true,data:()=>({computer_name:'PC',notification_events:[{id:'event-1',kind:'completed',file:'backup.zip'}]})}}};
    await handlers.notifyUpload.run(event);
    await handlers.notifyUpload.run(event);
    assert.equal(messages.length,1);
    assert.equal(messages[0].token,'test-token-active');
    assert.equal(messages[0].android.notification.tag,'event-1');
  } finally { messaging.send=original; }
});
