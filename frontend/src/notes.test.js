import test from "node:test";
import assert from "node:assert/strict";

import { canSaveNotes, plainTextFrom } from "./notesEdit.js";

test("nothing saves before the note has loaded", () => {
  assert.equal(canSaveNotes("loading", false), false);
  assert.equal(canSaveNotes("error", false), false);
  assert.equal(canSaveNotes("ready", false), true);
  assert.equal(canSaveNotes("ready", true), false);  // viewers never save
});

test("paste keeps plain text only", () => {
  const clipboard = { getData: (type) => type === "text/plain" ? "a thought" : "<b>a thought</b>" };
  assert.equal(plainTextFrom(clipboard), "a thought");
  assert.equal(plainTextFrom({ getData: () => "" }), "");
  assert.equal(plainTextFrom(null), "");
});
