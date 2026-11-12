const assert = require("node:assert/strict");
const { openBrowser, openBoard } = require("./helpers.cjs");

(async () => {
  const { browser, page } = await openBrowser();
  const failures = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };
  try {
    await openBoard(page);
    await page.getByRole("button", { name: /^ACTIVE\d+$/ }).click();

    const projectDisclosure = page.getByRole("button", { name: "Toggle Brand Refresh details", exact: true });
    check(await projectDisclosure.count() === 1, "project has a focusable disclosure button");
    if (await projectDisclosure.count()) {
      await projectDisclosure.focus();
      await page.keyboard.press("Enter");
      check(await page.getByPlaceholder("PROJECT").isVisible(), "Enter opens project details");
      await page.keyboard.press("Space");
      check(!(await page.getByPlaceholder("PROJECT").isVisible()), "Space closes project details");
    }

    await page.getByRole("button", { name: /^TODAY\d+$/ }).click();
    const eventDisclosure = page.getByRole("button", { name: "Toggle Morning standup details", exact: true });
    check(await eventDisclosure.count() === 1, "event has a focusable disclosure button");
    if (await eventDisclosure.count()) {
      await eventDisclosure.focus();
      await page.keyboard.press("Enter");
      check(await page.getByRole("button", { name: "DELETE", exact: true }).isVisible(), "Enter opens event details");
      await page.keyboard.press("Space");
      check(!(await page.getByRole("button", { name: "DELETE", exact: true }).isVisible()), "Space closes event details");
    }

    const recap = page.getByRole("button", { name: "REC", exact: true });
    await recap.focus();
    await recap.click();
    await page.getByText("Daily Recap", { exact: true }).waitFor();
    const dialog = page.getByRole("dialog", { name: "Daily Recap", exact: true });
    check(await dialog.count() === 1, "recap has role=dialog and an accessible title");
    if (await dialog.count()) {
      check(await dialog.getAttribute("aria-modal") === "true", "dialog is aria-modal");
      check(await dialog.evaluate((el) => el.contains(document.activeElement)), "dialog receives initial focus");
      await page.keyboard.press("Tab");
      check(await dialog.evaluate((el) => el.contains(document.activeElement)), "Tab stays inside the dialog");
    }
    await page.keyboard.press("Escape");
    await page.waitForTimeout(200);
    check(await page.getByText("Daily Recap", { exact: true }).count() === 0, "Escape closes the dialog");
    check(await recap.evaluate((el) => document.activeElement === el), "closing returns focus to REC");

    assert.deepEqual(failures, []);
    console.log("PASS disclosures support Enter/Space; dialogs trap focus, close on Escape, and return focus");
  } finally {
    await browser.close();
  }
})().catch((err) => { console.error(err); process.exitCode = 1; });
