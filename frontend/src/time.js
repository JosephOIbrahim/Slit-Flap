// The board's local day and the next half-hour block. No DOM, no API,
// so it can be tested with `npm test` (Node's built-in test runner).

export function localDate(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// The upcoming :00 or :30, strictly after now: 10:00 -> 10:30, 10:30 -> 11:00.
export function nextHalfHour(d = new Date()) {
  const next = (Math.floor((d.getHours() * 60 + d.getMinutes()) / 30) + 1) * 30;
  const p = (n) => String(n).padStart(2, "0");
  return `${p(Math.floor(next / 60) % 24)}:${p(next % 60)}`;
}
