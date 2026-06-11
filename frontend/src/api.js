// ─────────────────────────────────────────────────────────────
// Thin client for the DEPARTURES REST API.
// One place for fetch plumbing — components speak in paths.
// ─────────────────────────────────────────────────────────────

const json = (r) => r.json();

const send = (method) => (path, body) =>
  fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(json);

export const api = {
  get: (path) => fetch(`/api${path}`).then(json),
  post: send("POST"),
  put: send("PUT"),
  del: (path) => fetch(`/api${path}`, { method: "DELETE" }),
};
