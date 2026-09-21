const {test,before,after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {initializeTestEnvironment,assertSucceeds,assertFails} = require('@firebase/rules-unit-testing');
const {doc,getDoc,getDocs,collection,setDoc,updateDoc,deleteDoc,writeBatch,runTransaction,serverTimestamp,Timestamp} = require('firebase/firestore');
let env;
before(async()=>{
  env=await initializeTestEnvironment({projectId:'demo-driveflow',firestore:{host:'127.0.0.1',port:8085,rules:fs.readFileSync('../firestore.rules','utf8')}});
});
after(async()=>env?.cleanup());
const phone = uid=>env.authenticatedContext(uid).firestore();
async function seed(hash,id,expired=false) {
  await env.withSecurityRulesDisabled(async context=>{
    const db=context.firestore();
    await setDoc(doc(db,`pairing_codes/${hash}`),{protocol:'spark-v2',computer_id:id,computer_name:'PC',expiresAt:Timestamp.fromMillis(Date.now()+(expired?-60000:600000))});
    await setDoc(doc(db,`computers/${id}`),{status:'uploading'});
  });
}
async function redeem(db,uid,hash,wrongId=null,mirror=true) {
  return runTransaction(db,async tx=>{
    const codeRef=doc(db,`pairing_codes/${hash}`);
    const code=(await tx.get(codeRef)).data();
    const id=wrongId||code.computer_id;
    const link=doc(db,`readers/${uid}/computers/${id}`);
    const existing=await tx.get(link);
    if(code.usedBy===uid&&existing.exists())return id;
    tx.update(codeRef,{usedBy:uid,usedAt:serverTimestamp()});
    tx.set(link,{computer_name:'PC',codeHash:hash,pairedAt:serverTimestamp()});
    if(mirror)tx.set(doc(db,`computers/${id}/readers/${uid}`),{deviceName:'M32',codeHash:hash,pairedAt:serverTimestamp()});
    return id;
  });
}
test('Spark: atomic QR redemption grants only the correct machine, with idempotent retry',async()=>{
  const hash='a'.repeat(64),db=phone('spark-owner');
  await seed(hash,'spark-pc');
  await assertFails(getDoc(doc(db,'computers/spark-pc')));
  await assertSucceeds(redeem(db,'spark-owner',hash));
  await assertSucceeds(redeem(db,'spark-owner',hash));
  await assertSucceeds(getDoc(doc(db,'computers/spark-pc')));
  await assertFails(getDoc(doc(phone('stranger'),'computers/spark-pc')));
  await assertFails(getDocs(collection(db,'computers')));
  await assertFails(getDocs(collection(db,'pairing_codes')));
  await assertFails(setDoc(doc(db,'computers/spark-pc'),{status:'error'}));
  await assertFails(setDoc(doc(db,'readers/spark-owner/computers/other'),{computer_name:'PC',codeHash:hash,pairedAt:serverTimestamp()}));
});
test('Spark: two phones cannot consume the same code',async()=>{
  const hash='b'.repeat(64);await seed(hash,'race-pc');
  const result=await Promise.allSettled(['race1','race2'].map(uid=>redeem(phone(uid),uid,hash)));
  assert.equal(result.filter(r=>r.status==='fulfilled').length,1);
});
test('Spark: rejects expired codes, wrong machines, partial writes and forged code metadata',async()=>{
  const db=phone('attacker'),expired='c'.repeat(64),valid='d'.repeat(64);
  await seed(expired,'expired-pc',true);await seed(valid,'actual-pc');
  await assertFails(redeem(db,'attacker',expired));
  await assertFails(redeem(db,'attacker',valid,'wrong-pc'));
  await assertFails(redeem(db,'attacker',valid,null,false));
  await assertFails(updateDoc(doc(db,`pairing_codes/${valid}`),{usedBy:'attacker',usedAt:serverTimestamp()}));
  await assertFails(updateDoc(doc(db,`pairing_codes/${valid}`),{computer_id:'wrong-pc'}));
  await assertFails(setDoc(doc(db,'pairing_codes/'+'e'.repeat(64)),{protocol:'spark-v2',computer_id:'victim'}));
  await assertFails(redeem(env.unauthenticatedContext().firestore(),'attacker',valid));
  await assertFails(setDoc(doc(db,'readers/attacker/computers/actual-pc'),{computer_name:'PC',codeHash:valid,pairedAt:serverTimestamp()}));
  await assertSucceeds(redeem(db,'attacker',valid));
});
test('Spark: unlink/revoke prevents reuse of old code, fresh QR can restore access',async()=>{
  const db=phone('revoked-spark'),hash='f'.repeat(64);
  await seed(hash,'revoke-pc');await redeem(db,'revoked-spark',hash);
  const batch=writeBatch(db);
  batch.delete(doc(db,'readers/revoked-spark/computers/revoke-pc'));
  batch.delete(doc(db,'computers/revoke-pc/readers/revoked-spark'));
  await assertSucceeds(batch.commit());
  await assertFails(getDoc(doc(db,'computers/revoke-pc')));
  await assertFails(redeem(db,'revoked-spark',hash));
  const fresh='1'.repeat(64);await seed(fresh,'revoke-pc');
  await assertSucceeds(redeem(db,'revoked-spark',fresh));
  await assertFails(deleteDoc(doc(phone('stranger'),'readers/revoked-spark/computers/revoke-pc')));
});
