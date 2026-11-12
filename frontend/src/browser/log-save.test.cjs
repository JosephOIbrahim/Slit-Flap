const assert = require("node:assert/strict");
const { openBrowser, openBoard } = require("./helpers.cjs");

(async () => {
  const { browser, page } = await openBrowser();
  try {
    await openBoard(page);
    await page.getByRole("button", { name: /^ACTIVE\d+$/ }).click();
    await page.getByText("Finalize color palette + type system", { exact: true }).click();
    const logInput = page.getByPlaceholder("Log a note...");
    await logInput.waitFor();
    await page.waitForTimeout(700);  // let opening the card finish its lastTouched save

    const requests = [];
    const recording = (request) => {
      if (request.url().includes("/api/projects")) {
        requests.push({ method: request.method(), url: request.url() });
      }
    };
    page.on("request", recording);
    await logInput.fill("Evidence for the recap");
    await Promise.all([
      page.waitForResponse((res) => res.url().endsWith("/api/projects/brand-refresh/logs") && res.request().method() === "POST"),
      logInput.locator("..").getByRole("button", { name: "+", exact: true }).click(),
    ]);
    await page.waitForTimeout(700);
    page.off("request", recording);

    const puts = requests.filter((r) => r.method === "PUT" && r.url.endsWith("/api/projects/brand-refresh"));
    const refetches = requests.filter((r) => r.method === "GET" && r.url.endsWith("/api/projects"));
    assert.deepEqual(puts, [], "a log POST must not be followed by a stale project PUT");
    assert.ok(refetches.length > 0, "the project version must be synchronized after the log POST");
    assert.equal(await page.getByText("BOARD RELOADED · THIS PAGE WAS BEHIND").count(), 0);
    console.log("PASS log POST appends locally, refetches the version, and sends no project PUT");
  } finally {
    await browser.close();
  }
})().catch((err) => { console.error(err); process.exitCode = 1; });
