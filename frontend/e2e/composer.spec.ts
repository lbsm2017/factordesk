import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const SHOTS = process.env["SHOTS_DIR"] ?? fileURLToPath(new URL("../shots/", import.meta.url));
const FIRST_REPORT_MS = 120_000;

/** Nothing may leave the machine: any request to another host is aborted and fails the test. */
async function blockForeign(page: Page): Promise<string[]> {
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
  return foreign;
}

async function create(page: Page, preset: string, name: string): Promise<void> {
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("radio", { name: new RegExp(`^${preset}`) }).check();
  await page.getByRole("button", { name: "Create portfolio" }).click();
}

test("build a 2-holding portfolio and run it on the fake backend", async ({ page }) => {
  const foreign = await blockForeign(page);

  // The third mode of the switch, with its own URL value.
  await page.goto("/");
  await page.getByRole("radio", { name: "Portfolio" }).check();
  await expect(page).toHaveURL(/[?&]m=portfolio\b/);
  await expect(page.getByTestId("portfolio-landing")).toBeVisible();

  // A blank portfolio, then two lines from the library picker.
  await create(page, "Blank", "Two holdings");
  await expect(page.locator("h1")).toContainText("Two holdings");
  await expect(page.locator(".tree-empty")).toBeVisible();
  await page.getByRole("button", { name: "Add sub-asset class" }).click();
  const picker = page.getByRole("dialog", { name: "Add sub-asset class" });
  await expect(picker).toBeVisible();
  // Lines with no proxy are listed and cannot be added.
  await expect(picker.getByText("No proxy yet").first()).toBeVisible();
  await picker.getByLabel("Search the library").fill("IVV");
  await picker.getByRole("button", { name: "Add Equity N. America - Large Cap" }).click();
  await picker.getByLabel("Search the library").fill("IEF");
  await picker.getByRole("button", { name: "Add N. American Government Bonds" }).click();
  await page.keyboard.press("Escape");
  await expect(picker).toHaveCount(0);

  // The library name, the proxy and its start year show on the line.
  const tree = page.locator(".tree-panel");
  await expect(tree).toContainText("Equity N. America - Large Cap");
  await expect(tree).toContainText("IVV");
  await expect(tree).toContainText("from 2000");

  // Weights: typed, and nudged with the arrow keys.
  const equity = page.getByLabel("Weight of Equity N. America - Large Cap, percent");
  const bonds = page.getByLabel("Weight of N. American Government Bonds, percent");
  await equity.fill("59");
  await equity.press("ArrowUp");
  await equity.press("ArrowUp");
  await expect(equity).toHaveValue("60.0");
  await bonds.fill("40");
  const live = page.getByRole("complementary", { name: "Live portfolio check" });
  await expect(live).toContainText("100.0%");
  await expect(live).toContainText("100% allocated");
  await expect(live).toContainText("Limited by IEF");

  // A refusal shows the API message; the composer stays.
  await page.getByRole("button", { name: "Swap the ticker of N. American Government Bonds" }).click();
  await page.getByLabel("New ticker").fill("XYZ");
  await page.getByRole("button", { name: "Swap", exact: true }).click();
  await live.getByRole("button", { name: "Run backtest" }).click();
  await expect(page.getByTestId("portfolio-error")).toContainText("No prices were returned for XYZ");
  await expect(tree).toBeVisible();

  // Back to the library proxy, then a good run: the composer folds and the report follows.
  await page.getByRole("button", { name: "Swap the ticker of N. American Government Bonds" }).click();
  await page.getByLabel("New ticker").fill("IEF");
  await page.getByRole("button", { name: "Swap", exact: true }).click();
  await live.getByRole("button", { name: "Run backtest" }).click();
  const fold = page.getByRole("group", { name: "Portfolio summary" });
  await expect(fold).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(fold).toContainText("Two holdings");
  await expect(fold).toContainText("2 lines");
  await expect(fold).toContainText("100% allocated");
  await expect(page.locator(".abar")).toBeVisible();
  await expect(page.locator("#header h1")).toContainText("Two holdings");
  await expect(page.locator(".tree-panel")).toHaveCount(0);

  // Edit reopens the composer with the weights as they were.
  await fold.getByRole("button", { name: "Edit" }).click();
  await expect(page.getByLabel("Weight of Equity N. America - Large Cap, percent")).toHaveValue("60.0");

  // The portfolio is saved in this browser: it survives a reload. Delete is at once, with Undo.
  await page.reload();
  const saved = page.getByRole("list", { name: "Saved portfolios" });
  await expect(saved.getByRole("button", { name: /Two holdings/ })).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByTestId("undo-region")).toContainText("Deleted Two holdings");
  await expect(page.getByTestId("portfolio-landing")).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(saved.getByRole("button", { name: /Two holdings/ })).toBeVisible();

  expect(foreign, "requests to a host other than 127.0.0.1").toEqual([]);
});

test("the composer at 1440 and 390 px, before and after a run @shots", async ({ page }) => {
  mkdirSync(SHOTS, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1400 });
  await page.goto("/?m=portfolio");
  await create(page, "Balanced SAA", "Balanced SAA");
  await expect(page.locator(".tree-panel")).toContainText("Equity N. America - Large Cap");
  await page.screenshot({ path: `${SHOTS}/composer-1440.png`, fullPage: true });

  await page.getByRole("button", { name: "Add sub-asset class" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/picker-1440.png` });
  await page.keyboard.press("Escape");

  await page.getByRole("complementary", { name: "Live portfolio check" }).getByRole("button", { name: "Run backtest" }).click();
  await expect(page.getByRole("group", { name: "Portfolio summary" })).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.locator(".abar")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/after-run-1440.png`, fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Edit" }).click();
  await expect(page.locator(".tree-panel")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/composer-390.png`, fullPage: true });
  await page.screenshot({ path: `${SHOTS}/composer-390-viewport.png` });
  await page.locator(".run-dock").getByRole("button", { name: "Run backtest" }).click();
  await expect(page.getByRole("group", { name: "Portfolio summary" })).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.locator(".abar")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/after-run-390.png`, fullPage: true });
});
