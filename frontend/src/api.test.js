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
  assert.deepEqual(JSON.parse(calls[0].options.body), { content: "a", updatedAt: "v1" });
});

import { _resetSaveState, flushSaveQueue, saveState } from "./api.js";

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
