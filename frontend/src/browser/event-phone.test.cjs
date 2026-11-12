const assert = require("node:assert/strict");
const { openBrowser, openBoard } = require("./helpers.cjs");

(async () => {
  const { browser, page } = await openBrowser({ width: 390, height: 844 });
  try {
    await openBoard(page);
    const eventName = page.getByText("Morning standup", { exact: true });
    await eventName.click();
    const deleteButton = page.getByRole("button", { name: "DELETE", exact: true });
    await deleteButton.waitFor();
    const box = await deleteButton.boundingBox();
    assert.ok(box, "DELETE has a layout box");
    assert.ok(box.x >= 0 && box.x + box.width <= 390,
      `DELETE must fit the 390px viewport, got x=${box.x}, width=${box.width}`);

    const card = await eventName.locator("xpath=../..").boundingBox();
    assert.ok(box.x >= card.x && box.x + box.width <= card.x + card.width,
      "DELETE must stay inside the event card");
    console.log("PASS event DELETE is reachable inside its card at 390px");
  } finally {
    await browser.close();
  }
})().catch((err) => { console.error(err); process.exitCode = 1; });
