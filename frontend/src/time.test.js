import test from "node:test";
import assert from "node:assert/strict";

import { localDate, nextHalfHour } from "./time.js";

test("localDate is the owner's day, not UTC", () => {
  assert.equal(localDate(new Date(2026, 10, 12, 23, 59)), "2026-11-12");
  assert.equal(localDate(new Date(2026, 0, 1, 0, 1)), "2026-01-01");
});

test("nextHalfHour is the upcoming :00 or :30, strictly after now", () => {
  assert.equal(nextHalfHour(new Date(2026, 10, 12, 10, 0)), "10:30");
  assert.equal(nextHalfHour(new Date(2026, 10, 12, 10, 29)), "10:30");
  assert.equal(nextHalfHour(new Date(2026, 10, 12, 10, 30)), "11:00");
  assert.equal(nextHalfHour(new Date(2026, 10, 12, 23, 50)), "00:00");
});
