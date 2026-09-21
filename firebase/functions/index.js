"use strict";
const {initializeApp} = require("firebase-admin/app");
const {getFirestore, Timestamp, FieldValue} = require("firebase-admin/firestore");
const {getMessaging} = require("firebase-admin/messaging");
const {onCall, HttpsError} = require("firebase-functions/v2/https");
const {onDocumentWritten} = require("firebase-functions/v2/firestore");
const {onSchedule} = require("firebase-functions/v2/scheduler");
const {setGlobalOptions} = require("firebase-functions/v2");
const {hash, validToken, validComputer, checkPairing, newEvents, labels} = require("./logic");
initializeApp();
setGlobalOptions({region: "us-central1", maxInstances: 3});
const db = getFirestore();
const uidOf = request => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Conecte o aplicativo primeiro.");
  return request.auth.uid;
};
// Random 256-bit QR secrets + expiry + transaction prevent guessing and replay.
exports.pairComputer = onCall(async request => {
  const uid = uidOf(request);
  const token = request.data?.token;
  if (!validToken(token)) throw new HttpsError("invalid-argument", "Código inválido.");
  const ref = db.collection("pairing_codes").doc(hash(token));
  return db.runTransaction(async tx => {
    const snap = await tx.get(ref);
    const code = snap.data();
    const error = checkPairing(code, uid, Date.now());
    if (error) throw new HttpsError(error, "Código expirado ou utilizado. Gere outro no Windows.");
    const id = code.computer_id;
    const link = db.doc(`readers/${uid}/computers/${id}`);
    // A consumed code cannot recreate a membership revoked after redemption.
    if (code.usedBy === uid) {
      if (!(await tx.get(link)).exists) throw new HttpsError("failed-precondition", "Vínculo revogado. Gere outro código.");
      return {computerId: id};
    }
    const deviceName = String(request.data?.deviceName || "Android").slice(0, 100);
    tx.set(link, {computer_name: code.computer_name, pairedAt: FieldValue.serverTimestamp()});
    tx.set(db.doc(`computers/${id}/readers/${uid}`), {deviceName, pairedAt: FieldValue.serverTimestamp()});
    tx.update(ref, {usedBy: uid, usedAt: FieldValue.serverTimestamp()});
    return {computerId: id};
  });
});
exports.unpairComputer = onCall(async request => {
  const uid = uidOf(request);
  const id = request.data?.computerId;
  if (!validComputer(id)) throw new HttpsError("invalid-argument", "Computador inválido.");
  const batch = db.batch();
  batch.delete(db.doc(`readers/${uid}/computers/${id}`));
  batch.delete(db.doc(`computers/${id}/readers/${uid}`));
  await batch.commit();
  return {ok: true};
});
exports.registerDevice = onCall(async request => {
  const uid = uidOf(request);
  const {token, deviceName, notifications} = request.data || {};
  if (typeof token !== "string" || token.length < 20 || token.length > 4096) throw new HttpsError("invalid-argument", "Token inválido.");
  // One app installation per anonymous identity. Rotation replaces the old token.
  await db.doc(`readers/${uid}`).set({token, deviceName: String(deviceName || "Android").slice(0, 100),
    notifications: notifications !== false, updatedAt: FieldValue.serverTimestamp()}, {merge: true});
  return {ok: true};
});

async function sendEvent(computerId, state, event) {
  if (!labels[event.kind]) return;
  const members = await db.collection(`computers/${computerId}/readers`).get();
  for (const member of members.docs) {
    const readerRef = db.doc(`readers/${member.id}`);
    const [reader, access] = await Promise.all([readerRef.get(), db.doc(`readers/${member.id}/computers/${computerId}`).get()]);
    const data = reader.data();
    if (!access.exists || !data?.token || data.notifications === false) continue;
    const receipt = db.doc(`notification_deliveries/${hash(`${computerId}:${event.id}:${member.id}`)}`);
    const claimed = await db.runTransaction(async tx => {
      const old = (await tx.get(receipt)).data();
      if (old?.sent) return false;
      // Force a later retry instead of acknowledging an unfinished delivery.
      if ((old?.leaseUntil?.toMillis() || 0) > Date.now()) throw new Error("Delivery lease active");
      tx.set(receipt, {leaseUntil: Timestamp.fromMillis(Date.now() + 60000),
        expiresAt: Timestamp.fromMillis(Date.now() + 7 * 86400000)});
      return true;
    });
    if (!claimed) continue;
    try {
      const name = String(state.computer_name || computerId).slice(0, 100);
      const file = String(event.file || "").slice(0, 160);
      await getMessaging().send({token: data.token,
        notification: {title: `${name} • ${labels[event.kind]}`, body: file || "Toque para ver os detalhes no DriveFlow."},
        data: {computer_id: computerId, event_id: event.id, kind: event.kind},
        android: {priority: "high", ttl: 3600000, notification: {channelId: "uploads", tag: event.id}}});
      await receipt.set({sent: true}, {merge: true});
    } catch (error) {
      if (["messaging/registration-token-not-registered", "messaging/invalid-registration-token"].includes(error.code)) {
        await db.runTransaction(async tx => {
          const current = await tx.get(readerRef);
          if (current.get("token") === data.token) tx.update(readerRef, {token: FieldValue.delete()});
        });
        await receipt.set({sent: true}, {merge: true});
      } else {
        await receipt.delete();
        throw error;
      }
    }
  }
}
exports.notifyUpload = onDocumentWritten({document: "computers/{computerId}", retry: true}, async event => {
  if (!event.data?.after.exists) return;
  const before = event.data.before.data();
  const after = event.data.after.data();
  for (const item of newEvents(before, after)) await sendEvent(event.params.computerId, after, item);
});
exports.detectDisconnected = onSchedule({schedule: "every 1 minutes", retryCount: 3}, async () => {
  // No extra heartbeat when idle. A stale idle snapshot does not imply offline.
  const active = await db.collection("computers").where("status", "in", ["uploading", "preparing"]).get();
  for (const snapshot of active.docs) {
    const state = snapshot.data();
    const timestamp = state.last_update?.toMillis();
    const threshold = Math.max(90000, Math.min(3600000, Number(state.update_interval_seconds || 5) * 3000));
    if (!timestamp || Date.now() - timestamp < threshold) continue;
    // Stable across retries until the machine publishes again.
    await sendEvent(snapshot.id, state, {id: `lost-${timestamp}`, kind: "connection_lost", file: state.current_file});
  }
  // Bounded cleanup; also enable Firestore TTL for larger installations.
  for (const collection of ["pairing_codes", "notification_deliveries"]) {
    const expired = await db.collection(collection).where("expiresAt", "<", Timestamp.now()).limit(200).get();
    if (!expired.empty) {
      const batch = db.batch(); expired.docs.forEach(d => batch.delete(d.ref)); await batch.commit();
    }
  }
});
