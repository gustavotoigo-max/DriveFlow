"use strict";
const crypto = require("node:crypto");
const hash = value => crypto.createHash("sha256").update(value).digest("hex");
const validToken = token => typeof token === "string" && /^[A-Za-z0-9_-]{43}$/.test(token);
const validComputer = id => typeof id === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(id);
function checkPairing(code, uid, now) {
  if (!code || !validComputer(code.computer_id)) return "not-found";
  if (code.usedBy === uid) return null; // Safe retry of the same redemption.
  if (code.usedBy || !code.expiresAt || code.expiresAt.toMillis() <= now) return "failed-precondition";
  return null;
}
function newEvents(before, after) {
  const seen = new Set((before?.notification_events || []).map(e => e.id));
  return (after?.notification_events || []).filter(e => typeof e.id === "string" && !seen.has(e.id));
}
const labels = {started: "Upload iniciado", resumed: "Upload retomado", paused: "Upload pausado",
  cancelled: "Upload cancelado", error: "Upload interrompido por erro", completed: "Arquivo concluído",
  queue_completed: "Fila concluída", offline: "Computador desconectado", connection_lost: "Computador sem contato"};
module.exports = {hash, validToken, validComputer, checkPairing, newEvents, labels};
