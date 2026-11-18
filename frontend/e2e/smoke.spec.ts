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
  const kpis = page.locator("#kpis");
  // The first report of a run is computed from scratch and can take long on a busy machine.
  await expect(kpis).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(kpis).toContainText("Alpha, a year");
  await expect(kpis).toContainText("R²");
  await expect(page.locator("#equation")).toBeVisible();

  // The residual panel loads as its own chunk and shows the table and the stability section.
  const residual = page.locator("#residual");
  await expect(residual.getByRole("heading", { name: "In-sample against point-in-time", exact: true })).toBeVisible();
  await expect(residual.getByRole("heading", { name: "Is the alpha stable?" })).toBeVisible();

  // Range chip.
  await page.getByRole("radio", { name: "3Y" }).check();
  await expect(page).toHaveURL(/[?&]range=3Y\b/);
  await expect(page.getByRole("radio", { name: "3Y" })).toBeChecked();
  await expect(kpis).toBeVisible();
  await expect(kpis).toContainText("Analysed range");

  // A Details disclosure opens.
  const details = page.locator("details", { has: page.locator("summary", { hasText: /^Details$/ }) }).first();
  await expect(details).toBeVisible();
  await details.locator("summary").click();
  await expect(details).toHaveJSProperty("open", true);

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
  await expect(kpis).toContainText("Analysed range");
  expect(new Set(apiStarts)).toEqual(new Set(["2013-01-01"]));

  // No sideways scroll at 1440 and at 390; screenshots of the synthetic report.
  await page.evaluate(() => window.scrollTo(0, 0));
  await noSideScroll(page);
  await page.screenshot({ path: `${SHOTS}smoke-1440.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(kpis).toBeVisible();
  await noSideScroll(page);
  await page.screenshot({ path: `${SHOTS}smoke-390.png`, fullPage: true });

  expect(foreign, "requests to a host other than 127.0.0.1").toEqual([]);
});
