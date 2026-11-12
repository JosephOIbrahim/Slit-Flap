import test from "node:test";
import assert from "node:assert/strict";

import { changedFields, flushPendingSaves } from "./projectFields.js";

test("only the changed fields are sent", () => {
  const before = { id: "p", name: "Old", next: "one", updatedAt: "v1", history: [] };
  assert.deepEqual(changedFields(before, { ...before, name: "New" }), { name: "New" });
});

test("version and history are never part of the patch", () => {
  const before = { id: "p", name: "Same", updatedAt: "v1", history: [{ to: "ACTIVE" }] };
  assert.deepEqual(changedFields(before, { ...before, updatedAt: "v2", history: [] }), {});
});

test("no previous row means no patch", () => {
  assert.deepEqual(changedFields(undefined, { id: "p", name: "New" }), {});
});

test("pagehide flushes every pending field patch with keepalive", () => {
  const pending = new Map([
    ["one", { patch: { name: "First" }, timer: setTimeout(() => {}, 10000) }],
    ["two", { patch: { next: "Second", track: "04" }, timer: setTimeout(() => {}, 10000) }],
  ]);
  const sent = [];
  flushPendingSaves(pending, (id, patch, options) => sent.push({ id, patch, options }));
  assert.equal(pending.size, 0);
  assert.deepEqual(sent, [
    { id: "one", patch: { name: "First" }, options: { keepalive: true } },
    { id: "two", patch: { next: "Second", track: "04" }, options: { keepalive: true } },
  ]);
});
