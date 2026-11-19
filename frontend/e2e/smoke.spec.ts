import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const FIRST_REPORT_MS = 120_000;
const SHOTS = fileURLToPath(new URL("../shots/", import.meta.url));

async function noSideScroll(page: Page): Promise<void> {
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(scroll, `scrollWidth ${scroll} exceeds clientWidth ${client}`).toBeLessThanOrEqual(client);
}

test("dashboard smoke on the fake backend", async ({ page }) => {
  // Nothing may leave the machine: any request to another host is aborted and fails the test.
  const foreign: string[] = [];
  await page.route("**/*", async (route) => {
    const { hostname } = new URL(route.request().url());
    if (hostname === "127.0.0.1") {
      await route.continue();
      return;
    }
    foreign.push(route.request().url());
    await route.abort();
  });

  // Landing page and a ticker search.
  await page.goto("/");
  const ticker = page.getByRole("combobox", { name: "Ticker" });
  await expect(ticker).toBeVisible();
  // No ticker yet: the range controls are disabled, with the reason as visible text.
  await expect(page.getByRole("radio", { name: "3Y" })).toBeDisabled();
  await expect(page.getByLabel("From")).toBeDisabled();
  await expect(page.getByText("Choose a ticker first.")).toBeVisible();
  await ticker.fill("SYN");
  await ticker.press("Enter");
  await expect(page).toHaveURL(/[?&]t=SYN\b/);
  const bar = page.locator(".abar");
  // The first report of a run is computed from scratch and can take long on a busy machine.
  await expect(bar).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(bar).toContainText("Analysis period");
  await expect(bar).toContainText("Observations");
  // The formula is gone (owner, dashboard v2); the sidebar sits outside <main>.
  const summary = page.locator("#summary");
  await expect(summary).toContainText("Alpha (annual)");
  await expect(summary).toContainText("R²");
  await expect(page.locator("#equation")).toHaveCount(0);
  await expect(page.locator("main aside, main #sidebar")).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: "Price" })).toBeVisible();

  // Show statistics: off by default; on adds the t column and stats=1 without a new history entry.
  const exposures = page.locator("#exposures");
  const stats = page.getByRole("switch", { name: "Show statistics" });
  await expect(stats).toHaveAttribute("aria-checked", "false");
  await expect(exposures.getByRole("columnheader", { name: "t", exact: true })).toHaveCount(0);
  const entries = await page.evaluate(() => window.history.length);
  await stats.focus();
  await page.keyboard.press("Space");
  await expect(stats).toHaveAttribute("aria-checked", "true");
  await expect(page).toHaveURL(/[?&]stats=1\b/);
  await expect(exposures.getByRole("columnheader", { name: "t", exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.history.length)).toBe(entries);
  await page.keyboard.press("Enter");
  await expect(stats).toHaveAttribute("aria-checked", "false");
  await expect(page).not.toHaveURL(/[?&]stats=/);
  await stats.click();
  await expect(page).toHaveURL(/[?&]stats=1\b/);

  // The residual panel loads as its own chunk and shows the table and the stability section.
  const residual = page.locator("#residual");
  await expect(residual.getByRole("heading", { name: "In-sample against point-in-time", exact: true })).toBeVisible();
  await expect(residual.getByRole("heading", { name: "Is the alpha stable?" })).toBeVisible();

  // Range chip.
  await page.getByRole("radio", { name: "3Y" }).check();
  await expect(page).toHaveURL(/[?&]range=3Y\b/);
  await expect(page.getByRole("radio", { name: "3Y" })).toBeChecked();
  // The switch stays on across a range change.
  await expect(page).toHaveURL(/[?&]stats=1\b/);
  await expect(bar).toBeVisible();
  await expect(page.getByRole("radio", { name: "10Y" })).toBeVisible();
  await expect(page.locator("#summary")).toContainText("Past data, not a forecast");

  // A Details disclosure opens.
  const details = page.locator("#summary").getByRole("button", { name: "Details" });
  await expect(details).toBeVisible();
  await details.click();
  await expect(details).toHaveAttribute("aria-expanded", "true");

  // The "/" shortcut focuses the ticker field from outside a text field.
  await page.locator("body").click({ position: { x: 2, y: 2 } });
  await expect(ticker).not.toBeFocused();
  await page.keyboard.press("/");
  await expect(ticker).toBeFocused();
  // It also works from a radio, which is not a text field.
  await page.getByRole("radio", { name: "3Y" }).focus();
  await expect(ticker).not.toBeFocused();
  await page.keyboard.press("/");
  await expect(ticker).toBeFocused();
  await expect(ticker).not.toHaveValue(/\//);

  // Rolling window by keyboard: arrow keys move between the radios and change `win`.
  const rolling = page.getByRole("group", { name: "Rolling window length" });
  await rolling.scrollIntoViewIfNeeded();
  const checked = rolling.getByRole("radio", { checked: true });
  const before = await checked.getAttribute("value");
  await checked.focus();
  await page.keyboard.press(before === "126" ? "ArrowRight" : "ArrowLeft");
  const after = before === "126" ? "252" : "126";
  await expect(rolling.getByRole("radio", { checked: true })).toHaveAttribute("value", after);
  await expect(page).toHaveURL(new RegExp(`[?&]win=${after}\\b`));

  // Download link keeps the range.
  await expect(page.getByRole("link", { name: "Download report" })).toHaveAttribute(
    "href",
    /\/api\/report\/SYN\/html\?.*range=3Y/,
  );

  // A typed year is partial input: Chrome emits 0002, 0020, 0202 on the way to 2013, and none of
  // them may reach the URL, the history or the server. Enter commits the finished date once.
  const apiStarts: string[] = [];
  page.on("request", (request) => {
    const start = new URL(request.url()).searchParams.get("start");
    if (start !== null) apiStarts.push(start);
  });
  const historyBefore = await page.evaluate(() => window.history.length);
  const from = page.getByRole("group", { name: "Custom dates" }).getByLabel("From");
  await from.focus();
  await page.keyboard.type("01012013");
  await expect(from).toHaveValue("2013-01-01");
  expect(page.url()).not.toMatch(/[?&]start=/);
  expect(await page.evaluate(() => window.history.length)).toBe(historyBefore);
  expect(apiStarts).toEqual([]);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/[?&]start=2013-01-01(&|$)/);
  expect(await page.evaluate(() => window.history.length)).toBe(historyBefore + 1);
  await expect(bar).toContainText("Analysis period");
  await expect(page.locator("#summary")).toContainText("Past data, not a forecast");
  expect(new Set(apiStarts)).toEqual(new Set(["2013-01-01"]));

  // No sideways scroll at 1440 and at 390; screenshots of the synthetic report.
  await page.evaluate(() => window.scrollTo(0, 0));
  await noSideScroll(page);
  await page.screenshot({ path: `${SHOTS}smoke-1440.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(bar).toBeVisible();
  await noSideScroll(page);
  await page.screenshot({ path: `${SHOTS}smoke-390.png`, fullPage: true });

  // Under 900 px the sidebar is a drawer: the menu button opens it, Escape closes it and focus returns.
  const menu = page.getByRole("button", { name: "Menu", exact: true });
  await expect(page.getByRole("combobox", { name: "Ticker" })).toBeHidden();
  await menu.click();
  await expect(menu).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("combobox", { name: "Ticker" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await expect(menu).toBeFocused();
  await noSideScroll(page);

  expect(foreign, "requests to a host other than 127.0.0.1").toEqual([]);
});
