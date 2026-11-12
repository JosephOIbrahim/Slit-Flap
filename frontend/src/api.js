// ─────────────────────────────────────────────────────────────
// Thin client for the DEPARTURES REST API.
// One place for fetch plumbing — components speak in paths.
//
// A failed request throws an Error carrying `status` and the
// server's JSON body, so callers can tell a 409 ("this page is
// behind the board") from any other failure.
// ─────────────────────────────────────────────────────────────

const request = async (method, path, body) => {
  const res = await fetch(`/api${path}`, {
    method,
    ...(body === undefined
      ? {}
      : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error((data && data.error) || `${method} /api${path} failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
};

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  put: (path, body) => request("PUT", path, body),
  // For pagehide/visibilitychange: the request outlives the page.
  putKeepalive: (path, body) => fetch(`/api${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    keepalive: true,
  }).then(async (res) => {
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const err = new Error((data && data.error) || `PUT /api${path} failed (${res.status})`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }),
  del: (path) => request("DELETE", path),
};
