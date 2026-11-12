import test from "node:test";
import assert from "node:assert/strict";

import { canSaveNotes, createNotesSaveQueue, plainTextFrom } from "./notesEdit.js";

test("nothing saves before the note has loaded", () => {
  assert.equal(canSaveNotes("loading", false), false);
  assert.equal(canSaveNotes("error", false), false);
  assert.equal(canSaveNotes("ready", false), true);
  assert.equal(canSaveNotes("ready", true), false);  // viewers never save
});

test("note saves are serialized and the next snapshot uses the returned version", async () => {
  let stamp = "v1";
  let releaseFirst;
  const calls = [];
  const queue = createNotesSaveQueue({
    getDraft: () => "second",
    getNote: async () => ({ content: "server", updatedAt: "server-v1" }),
    putNote: async (content) => {
      calls.push({ content, updatedAt: stamp });
      if (calls.length === 1) {
        await new Promise((resolve) => { releaseFirst = resolve; });
      }
      stamp = calls.length === 1 ? "v2" : "v3";
      return { updatedAt: stamp };
    },
    onVersion: (value) => { stamp = value; },
  });

  const first = queue.save("first");
  const second = queue.save("second");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(calls.length, 1);
  releaseFirst();
  await Promise.all([first, second]);
  assert.deepEqual(calls, [
    { content: "first", updatedAt: "v1" },
    { content: "second", updatedAt: "v2" },
  ]);
});

test("a conflict preserves and replays the newer editor draft", async () => {
  let stamp = "v1";
  const calls = [];
  let conflictCount = 0;
  const queue = createNotesSaveQueue({
    getDraft: () => "newer draft",
    getNote: async () => ({ content: "someone else", updatedAt: "server-v9" }),
    putNote: async (content) => {
      calls.push({ content, updatedAt: stamp });
      if (calls.length === 1) {
        const err = new Error("stale");
        err.status = 409;
        throw err;
      }
      stamp = "v10";
      return { updatedAt: stamp };
    },
    onVersion: (value) => { stamp = value; },
    onConflict: () => { conflictCount += 1; },
  });

  await queue.save("older draft");
  assert.equal(conflictCount, 1);
  assert.deepEqual(calls, [
    { content: "older draft", updatedAt: "v1" },
    { content: "newer draft", updatedAt: "server-v9" },
  ]);
});

test("paste keeps plain text only", () => {
  const clipboard = { getData: (type) => type === "text/plain" ? "a thought" : "<b>a thought</b>" };
  assert.equal(plainTextFrom(clipboard), "a thought");
  assert.equal(plainTextFrom({ getData: () => "" }), "");
  assert.equal(plainTextFrom(null), "");
});
