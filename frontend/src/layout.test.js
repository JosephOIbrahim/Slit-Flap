import test from "node:test";
import assert from "node:assert/strict";

import { PHONE_WIDTH, isPhoneWidth, flapSizeFor } from "./layout.js";

test("phone width is 600 and below", () => {
  assert.equal(isPhoneWidth(390), true);
  assert.equal(isPhoneWidth(PHONE_WIDTH), true);
  assert.equal(isPhoneWidth(PHONE_WIDTH + 1), false);
});

test("a 14-letter name fits a 390px card", () => {
  const size = flapSizeFor({ width: 390, text: "BRAND REFRESH", preferred: 104 });
  const letters = "BRAND REFRESH".length;
  const used = letters * size * 0.7 + 4 * (letters - 1);
  assert.ok(size >= 24 && size < 104);
  assert.ok(used <= 390 - 72, `${used}px used`);
});

test("a short name keeps the chosen size", () => {
  assert.equal(flapSizeFor({ width: 390, text: "THIS", preferred: 104 }), 104);
});

test("desktop keeps the preferred size for a normal name", () => {
  assert.equal(flapSizeFor({ width: 1280, text: "BRAND REFRESH", preferred: 104 }), 104);
});
