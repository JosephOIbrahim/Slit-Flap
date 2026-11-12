const assert = require("node:assert/strict");
const { ORIGIN, openBrowser, openBoard } = require("./helpers.cjs");

(async () => {
  const { browser, page } = await openBrowser();
  try {
    await openBoard(page);
    await page.getByRole("button", { name: /^ACTIVE\d+$/ }).click();
    const created = page.waitForResponse((res) => res.url() === `${ORIGIN}/api/projects` && res.request().method() === "POST");
    const refreshed = page.waitForResponse((res) => res.url() === `${ORIGIN}/api/projects` && res.request().method() === "GET");
    await page.getByRole("button", { name: "+", exact: true }).click();
    await Promise.all([created, refreshed]);

    const editor = page.getByPlaceholder("PROJECT");
    await editor.waitFor();
    assert.equal(await editor.inputValue(), "New Project");
    const allWeight = await page.getByRole("button", { name: /^ALL\d+$/ }).evaluate((el) => getComputedStyle(el).fontWeight);
    assert.equal(allWeight, "700");
    console.log("PASS NEW switches from ACTIVE to ALL and opens the new QUEUED card");
  } finally {
    await browser.close();
  }
})().catch((err) => { console.error(err); process.exitCode = 1; });
