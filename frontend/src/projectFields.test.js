import test from "node:test";
import assert from "node:assert/strict";

import { changedFields } from "./projectFields.js";

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
