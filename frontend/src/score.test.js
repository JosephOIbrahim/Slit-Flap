import test from "node:test";
import assert from "node:assert/strict";

import { FILTERS, scoreProject, statusColor } from "./utils.js";

const p = (status) => ({ status, track: "04", lastTouched: "2026-11-12T12:00:00+00:00" });

test("REVIEW is a filter of its own", () => {
  assert.ok(FILTERS.includes("REVIEW"));
});

test("ARCHIVED has a filter of its own", () => {
  assert.ok(FILTERS.includes("ARCHIVED"));
});

test("REVIEW ranks as work waiting on you", () => {
  assert.ok(scoreProject(p("REVIEW")) > scoreProject(p("BLOCKED")));
  assert.ok(scoreProject(p("REVIEW")) < scoreProject(p("ACTIVE")));
  assert.ok(scoreProject(p("REVIEW")) > scoreProject(p("ROLLING")));
});

test("REVIEW is readable, not the empty-slot grey", () => {
  assert.notEqual(statusColor("REVIEW"), statusColor("QUEUED"));
  assert.equal(statusColor("REVIEW"), "#999");
});
