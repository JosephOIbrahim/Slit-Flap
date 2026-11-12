import test from "node:test";
import assert from "node:assert/strict";

import {
  FILTERS, scoreProject, statusColor, departure,
  nextUpProject, startHereText, filterCounts, visibleProjects, matchesFilter, groupByTrack,
} from "./utils.js";
import {
  ACCENT, WHITE, WHISPER, RISK, BG, G5, G6, NOTES_BG, HOVER, SWATCHES,
  contrast, WHISPER_MIN_CONTRAST,
} from "./theme.js";

const p = (status) => ({ status, track: "04", lastTouched: "2026-11-12T12:00:00+00:00" });

// Local-date helper, so a deadline test means the same thing in every timezone.
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const plusDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return ymd(d); };

// ─── FILTERS ─────────────────────────────────────────────────

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

// ─── ONE ACCENT, SPENT ONCE ──────────────────────────────────

test("no status word spends the accent", () => {
  for (const status of ["QUEUED", "ACTIVE", "ROLLING", "BLOCKED", "REVIEW", "SHIPPED"]) {
    assert.notEqual(statusColor(status), ACCENT, `${status} must not be amber`);
  }
});

test("status words are white, whisper, or risk", () => {
  assert.equal(statusColor("ACTIVE"), WHITE);
  assert.equal(statusColor("ROLLING"), WHITE);
  assert.equal(statusColor("REVIEW"), WHITE);
  assert.equal(statusColor("QUEUED"), WHISPER);
  assert.equal(statusColor("SHIPPED"), WHISPER);
  assert.equal(statusColor("BLOCKED"), RISK);
});

test("deadline words: late is risk, coming up is white, neither is amber", () => {
  assert.equal(departure({ deadline: plusDays(-2), status: "ACTIVE" }).color, RISK);
  assert.equal(departure({ deadline: plusDays(0), status: "ACTIVE" }).color, WHITE);
  assert.equal(departure({ deadline: plusDays(3), status: "ACTIVE" }).color, WHITE);
  assert.notEqual(departure({ deadline: plusDays(3), status: "ACTIVE" }).color, ACCENT);
  assert.equal(departure({ deadline: plusDays(3), status: "SHIPPED" }), null);
});

// ─── WHISPER SCALE ───────────────────────────────────────────

test("a whisper is 5.1:1 or better on every surface the board paints", () => {
  const surfaces = [BG, G5, G6, NOTES_BG, HOVER, ...SWATCHES.filter(Boolean)];
  for (const surface of surfaces) {
    const ratio = contrast(WHISPER, surface);
    assert.ok(ratio >= WHISPER_MIN_CONTRAST, `${WHISPER} on ${surface} is ${ratio.toFixed(2)}:1`);
  }
});

test("blocked and delayed read at 5.3:1 on the board and its panels", () => {
  assert.ok(contrast(RISK, BG) >= 5.3);
  assert.ok(contrast(RISK, G5) >= 5.3);
  const surfaces = [G6, NOTES_BG, HOVER, ...SWATCHES.filter(Boolean)];
  for (const surface of surfaces) {
    assert.ok(contrast(RISK, surface) >= WHISPER_MIN_CONTRAST, `${RISK} on ${surface}`);
  }
});

// ─── NEXT UP / START HERE ────────────────────────────────────

test("next up is the highest-scoring project that is waiting on you", () => {
  const board = [
    p("BLOCKED"),
    { ...p("ACTIVE"), id: "a" },
    { ...p("QUEUED"), id: "q" },
    { ...p("SHIPPED"), id: "s" },
  ];
  assert.equal(nextUpProject(board).id, "a");
});

test("next up ignores shipped and queued cards", () => {
  assert.equal(nextUpProject([p("SHIPPED"), p("QUEUED")]), null);
  assert.equal(nextUpProject([]), null);
});

test("START HERE names the project and its next action", () => {
  assert.equal(startHereText({ name: "Otto OS", next: "Wire the parser" }), "Otto OS — Wire the parser");
  assert.equal(startHereText({ name: "Otto OS", next: "" }), "Otto OS");
  assert.equal(startHereText({ name: "Otto OS", next: "Wire the parser" }, "in No time blocked"),
               "Otto OS — Wire the parser · in No time blocked");
  assert.equal(startHereText(null), "Nothing is waiting on you. Pick a card, or add one.");
});

// ─── FILTER COUNTS ───────────────────────────────────────────

const board = [
  { id: "a", status: "ACTIVE", todayTime: "09:00", todayDate: "2026-11-12" },
  { id: "b", status: "BLOCKED", todayTime: "", todayDate: "" },
  { id: "c", status: "REVIEW", todayTime: "14:00", todayDate: "2026-11-12" },
  { id: "d", status: "SHIPPED" },
];
const archived = [{ id: "e", status: "ACTIVE" }];

test("filter counts are true for every filter", () => {
  const counts = filterCounts(board, archived, "2026-11-12");
  assert.equal(counts.ALL, 3);
  assert.equal(counts.TODAY, 2);
  assert.equal(counts.ACTIVE, 1);
  assert.equal(counts.ROLLING, 0);
  assert.equal(counts.BLOCKED, 1);
  assert.equal(counts.REVIEW, 1);
  assert.equal(counts.QUEUED, 0);
  assert.equal(counts.SHIPPED, 1);
  assert.equal(counts.ARCHIVED, 1);
});

test("TODAY only counts blocks dated today", () => {
  assert.equal(matchesFilter({ status: "ACTIVE", todayTime: "09:00", todayDate: "2026-11-11" }, "TODAY", "2026-11-12"), false);
  assert.equal(matchesFilter({ status: "ACTIVE", todayTime: "09:00", todayDate: "2026-11-12" }, "TODAY", "2026-11-12"), true);
  assert.equal(matchesFilter({ status: "SHIPPED", todayTime: "09:00", todayDate: "2026-11-12" }, "TODAY", "2026-11-12"), false);
});

test("visible projects: ALL hides shipped, ARCHIVED is its own list", () => {
  assert.deepEqual(visibleProjects(board, archived, "ALL", "2026-11-12").map(x => x.id), ["a", "b", "c"]);
  assert.deepEqual(visibleProjects(board, archived, "ARCHIVED", "2026-11-12").map(x => x.id), ["e"]);
  assert.deepEqual(visibleProjects(board, archived, "REVIEW", "2026-11-12").map(x => x.id), ["c"]);
});


test("cards group under their track with counts, in track order", () => {
  const rows = [
    { id: "a", track: "02" }, { id: "b", track: "01" },
    { id: "c", track: "02" }, { id: "d", track: "04" },
  ];
  const groups = groupByTrack(rows);
  assert.deepEqual(groups.map((g) => g.track), ["01", "02", "04"]);
  assert.deepEqual(groups.map((g) => g.count), [1, 2, 1]);
  assert.deepEqual(groups[1].items.map((p) => p.id), ["a", "c"]);
  assert.deepEqual(groupByTrack([]), []);
});
