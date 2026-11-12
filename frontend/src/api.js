// ─────────────────────────────────────────────────────────────
// Thin client for the DEPARTURES REST API.
// One place for fetch plumbing — components speak in paths.
//
// A failed request throws an Error carrying `status` and the
// server's JSON body, so callers can tell a 409 ("this page is
// behind the board") from any other failure.
//
// Writes that fail for a reason worth retrying (offline, 5xx) go
// into a small queue. The header subscribes to saveState and shows
// one amber dot while anything is still unsaved.
// ─────────────────────────────────────────────────────────────

const state = { queue: new Map(), listeners: new Set(), seq: 0 };

export const saveState = {
  status: () => ({ pending: state.queue.size }),
  subscribe(listener) {
    state.listeners.add(listener);
    listener(saveState.status());
    return () => state.listeners.delete(listener);
  },
};

// Tests only: start each test with an empty queue.
export function _resetSaveState() {
  state.queue.clear();
  state.listeners.clear();
  state.seq = 0;
}

const notify = () => {
  const status = saveState.status();
  state.listeners.forEach((listener) => listener(status));
};

const isRetryable = (err) => !err.status || err.status >= 500;

const isProjectFieldPatch = (method, path) => method === "PUT" && /^\/projects\/[^/]+$/.test(path);

const remember = (method, path, body, generation) => {
  // Project PUTs are field patches, so two offline edits must be combined.
  // Full-document writes (notes, settings, event rows) still replace the
  // earlier body: replaying an old document over a newer one would undo it.
  const key = method === "PUT" ? `PUT ${path}` : `${method} ${path} #${generation}`;
  const previous = state.queue.get(key);
  const queuedBody = previous && isProjectFieldPatch(method, path)
    ? { ...previous.body, ...body }
    : body;
  state.queue.set(key, { key, method, path, body: queuedBody, generation });
  notify();
};

const request = async (method, path, body) => {
  let res;
  try {
    const headers = method === "GET" ? undefined : {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      "X-Departures": "1",
    };
    res = await fetch(`/api${path}`, {
      method,
      ...(headers ? { headers } : {}),
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (cause) {
    const err = new Error(`Could not reach the board (${method} /api${path})`);
    err.network = true;
    err.cause = cause;
    throw err;
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error((data && data.error) || `${method} /api${path} failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
};

const send = (method) => async (path, body) => {
  const key = method === "PUT" ? `PUT ${path}` : null;
  const generation = ++state.seq;
  try {
    const data = await request(method, path, body);
    const queued = key && state.queue.get(key);
    if (queued && queued.generation === generation) {
      state.queue.delete(key);
      notify();
    }
    return data;
  } catch (err) {
    if (isRetryable(err)) remember(method, path, body, generation);
    throw err;
  }
};

// Retry everything that failed for a retryable reason. Called on a timer and
// when the browser says it is back online; tests call it directly.
export async function flushSaveQueue() {
  if (!state.queue.size) return;
  for (const [key, item] of [...state.queue]) {
    try {
      await request(item.method, item.path, item.body);
      if (state.queue.get(key)?.generation === item.generation) state.queue.delete(key);
    } catch (err) {
      // A 4xx cannot help this generation, but a newer queued write survives.
      if (!isRetryable(err) && state.queue.get(key)?.generation === item.generation) {
        state.queue.delete(key);
      }
    }
  }
  notify();
}

export function startSaveQueue(intervalMs = 5000) {
  if (typeof window === "undefined" || typeof setInterval !== "function") return () => {};
  const timer = setInterval(() => { flushSaveQueue(); }, intervalMs);
  const onOnline = () => { flushSaveQueue(); };
  window.addEventListener("online", onOnline);
  return () => {
    clearInterval(timer);
    window.removeEventListener("online", onOnline);
  };
}

export const api = {
  get: (path) => request("GET", path),
  post: send("POST"),
  put: send("PUT"),
  del: send("DELETE"),
  // For pagehide/visibilitychange: the request outlives the page.
  putKeepalive: (path, body) => fetch(`/api${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-Departures": "1" },
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
};
