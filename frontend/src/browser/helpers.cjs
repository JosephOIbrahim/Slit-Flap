const { chromium } = require("playwright");

const ORIGIN = process.env.DEPARTURES_TEST_ORIGIN || "http://127.0.0.1:49790";

async function openBrowser({ width = 1280, height = 900 } = {}) {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
  });
  const context = await browser.newContext({ viewport: { width, height } });
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin === ORIGIN || ["data:", "blob:"].includes(url.protocol)) return route.continue();
    return route.abort();
  });
  const page = await context.newPage();
  return { browser, context, page };
}

async function openBoard(page) {
  await page.goto(ORIGIN, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /^ALL/ }).waitFor();
}

module.exports = { ORIGIN, openBrowser, openBoard };
