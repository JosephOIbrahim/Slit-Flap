// Which fields a page actually changed. Sending the whole project on every
// keystroke let parallel saves land out of order and carry stale values.
export function changedFields(before, after) {
  const out = {};
  if (!before || !after) return out;
  Object.keys(after).forEach((key) => {
    if (key === "updatedAt" || key === "history") return;
    if (JSON.stringify(after[key]) !== JSON.stringify(before[key])) out[key] = after[key];
  });
  return out;
}

// A hidden page may never run the 400ms debounce timers. Flush the actual
// merged patches, not a stale project snapshot, and let each request outlive
// the page. Deletes happen before sending so a timer callback cannot resend.
export function flushPendingSaves(pending, send) {
  for (const [id, entry] of [...pending]) {
    clearTimeout(entry.timer);
    pending.delete(id);
    send(id, entry.patch, { keepalive: true });
  }
}
