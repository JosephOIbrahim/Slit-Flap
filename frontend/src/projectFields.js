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
