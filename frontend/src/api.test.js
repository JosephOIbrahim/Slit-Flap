import test from "node:test";
import assert from "node:assert/strict";

import { api } from "./api.js";

test("a notes save on pagehide uses keepalive", async () => {
  const calls = [];
  const realFetch = global.fetch;
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ updatedAt: "v2" }) };
  };
  try {
    await api.putKeepalive("/projects/x/notes", { content: "a", updatedAt: "v1" });
  } finally {
    global.fetch = realFetch;
  }
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/projects/x/notes");
  assert.equal(calls[0].options.method, "PUT");
  assert.equal(calls[0].options.keepalive, true);
  assert.equal(calls[0].options.headers["Content-Type"], "application/json");
  assert.equal(calls[0].options.headers["X-Departures"], "1");
  assert.deepEqual(JSON.parse(calls[0].options.body), { content: "a", updatedAt: "v1" });
});

import { _resetSaveState, flushSaveQueue, saveState, startSaveQueue } from "./api.js";

const reply = (status, body = {}) => ({ ok: status < 400, status, json: async () => body });

test("a write that cannot reach the board is queued and retried", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  global.fetch = async () => { throw new TypeError("offline"); };
  try {
    await assert.rejects(api.put("/projects/p", { name: "one" }));
    assert.equal(saveState.status().pending, 1);
  } finally {
    global.fetch = realFetch;
  }

  let sent = null;
  global.fetch = async (url, options) => { sent = { url, options }; return reply(200, { ok: true }); };
  try {
    await flushSaveQueue();
  } finally {
    global.fetch = realFetch;
  }
  assert.equal(saveState.status().pending, 0);
  assert.equal(sent.url, "/api/projects/p");
  assert.deepEqual(JSON.parse(sent.options.body), { name: "one" });
});

test("a refused write (4xx) is not retried", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  global.fetch = async () => reply(409, { error: "stale" });
  try {
    await assert.rejects(api.put("/projects/p/notes", { content: "x" }));
    assert.equal(saveState.status().pending, 0);
  } finally {
    global.fetch = realFetch;
  }
});

test("a newer PUT replaces the queued body for the same path", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  global.fetch = async () => { throw new TypeError("offline"); };
  try {
    await assert.rejects(api.put("/projects/p", { name: "one" }));
    await assert.rejects(api.put("/projects/p", { name: "two" }));
  } finally {
    global.fetch = realFetch;
  }
  assert.equal(saveState.status().pending, 1);

  let sent = null;
  global.fetch = async (url, options) => { sent = options; return reply(200, {}); };
  try {
    await flushSaveQueue();
  } finally {
    global.fetch = realFetch;
  }
  assert.deepEqual(JSON.parse(sent.body), { name: "two" });
});

test("queued project field patches merge without losing earlier fields", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  global.fetch = async () => { throw new TypeError("offline"); };
  try {
    await assert.rejects(api.put("/projects/p", { name: "New name" }));
    await assert.rejects(api.put("/projects/p", { next: "Ship the board" }));
  } finally {
    global.fetch = realFetch;
  }
  assert.equal(saveState.status().pending, 1);

  let sent = null;
  global.fetch = async (url, options) => { sent = options; return reply(200, {}); };
  try {
    await flushSaveQueue();
  } finally {
    global.fetch = realFetch;
  }
  assert.deepEqual(JSON.parse(sent.body), { name: "New name", next: "Ship the board" });
});

test("queued notes writes still replace the whole document", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  global.fetch = async () => { throw new TypeError("offline"); };
  try {
    await assert.rejects(api.put("/projects/p/notes", { content: "first" }));
    await assert.rejects(api.put("/projects/p/notes", { content: "second" }));
  } finally {
    global.fetch = realFetch;
  }

  let sent = null;
  global.fetch = async (url, options) => { sent = options; return reply(200, {}); };
  try {
    await flushSaveQueue();
  } finally {
    global.fetch = realFetch;
  }
  assert.deepEqual(JSON.parse(sent.body), { content: "second" });
});

test("an older PUT success does not delete a newer queued write", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  let finishFirst;
  global.fetch = async (url, options) => {
    const body = JSON.parse(options.body);
    if (body.name === "first") {
      return new Promise((resolve) => { finishFirst = () => resolve(reply(200, {})); });
    }
    throw new TypeError("offline");
  };
  try {
    const first = api.put("/projects/p", { name: "first" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    await assert.rejects(api.put("/projects/p", { next: "newer offline edit" }));
    assert.equal(saveState.status().pending, 1);
    finishFirst();
    await first;
    assert.equal(saveState.status().pending, 1);
  } finally {
    global.fetch = realFetch;
  }
});

test("a successful PUT clears only its own queued generation", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  let offline = true;
  global.fetch = async () => {
    if (offline) throw new TypeError("offline");
    return reply(200, {});
  };
  try {
    await assert.rejects(api.put("/projects/p", { name: "offline" }));
    assert.equal(saveState.status().pending, 1);
    offline = false;
    await flushSaveQueue();
    assert.equal(saveState.status().pending, 0);
  } finally {
    global.fetch = realFetch;
  }
});

test("bodyless DELETE writes carry the board header", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  let seen = null;
  global.fetch = async (url, options) => { seen = options; return reply(200, {}); };
  try {
    await api.del("/projects/p");
  } finally {
    global.fetch = realFetch;
  }
  assert.equal(seen.method, "DELETE");
  assert.equal(seen.body, undefined);
  assert.equal(seen.headers["X-Departures"], "1");
});

test("save queue replays on online and timer, and cleanup removes both", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  const realWindow = global.window;
  const realSetInterval = global.setInterval;
  const realClearInterval = global.clearInterval;
  let online;
  let intervalCallback;
  let intervalMs;
  let clearedTimer = null;
  let removedOnline = null;
  const timer = { id: "save-queue" };
  global.window = {
    addEventListener: (name, callback) => { if (name === "online") online = callback; },
    removeEventListener: (name, callback) => { if (name === "online") removedOnline = callback; },
  };
  global.setInterval = (callback, ms) => {
    intervalCallback = callback;
    intervalMs = ms;
    return timer;
  };
  global.clearInterval = (value) => { clearedTimer = value; };

  let offline = true;
  global.fetch = async () => {
    if (offline) throw new TypeError("offline");
    return reply(200, {});
  };
  let stop = () => {};
  try {
    await assert.rejects(api.put("/projects/p", { name: "online replay" }));
    assert.equal(saveState.status().pending, 1);
    stop = startSaveQueue(4321);
    assert.equal(intervalMs, 4321);

    offline = false;
    online();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(saveState.status().pending, 0);

    offline = true;
    await assert.rejects(api.put("/projects/p", { name: "timer replay" }));
    assert.equal(saveState.status().pending, 1);
    offline = false;
    intervalCallback();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(saveState.status().pending, 0);

    stop();
    assert.equal(clearedTimer, timer);
    assert.equal(removedOnline, online);
  } finally {
    stop();
    global.fetch = realFetch;
    global.window = realWindow;
    global.setInterval = realSetInterval;
    global.clearInterval = realClearInterval;
  }
});

test("writes carry the board header", async () => {
  _resetSaveState();
  const realFetch = global.fetch;
  let seen = null;
  global.fetch = async (url, options) => { seen = options; return reply(200, {}); };
  try {
    await api.put("/projects/p", { name: "x" });
  } finally {
    global.fetch = realFetch;
  }
  assert.equal(seen.headers["X-Departures"], "1");
});
