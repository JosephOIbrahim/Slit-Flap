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
