import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const FIRST_REPORT_MS = 120_000;

/**
 * The fake backend serves USD only. The euro view is tested by answering the report and library
 * requests with the fake backend's own answer plus the fields the real backend adds in the euro view
 * (`currency` on the report, `hedge_eur` on a library line). Requests that carry `ccy=EUR` are
 * recorded so the test can check what the page asked for.
 */
async function euroBackend(page: Page): Promise<string[]> {
  const asked: string[] = [];
  await page.route(/\/api\/report\/SYN\?/, async (route) => {
    const url = route.request().url();
    const response = await route.fetch();
    const body = (await response.json()) as Record<string, unknown>;
    if (new URL(url).searchParams.get("ccy") === "EUR") {
      asked.push(url);
      body["currency"] = {
        reference: "EUR",
        fx_source: "Exchange rates: European Central Bank, euro foreign exchange reference rates.",
        rate_source: "Euro short-term rate and EONIA: European Central Bank, ECB Data Portal.",
        notes: ["Cash earns the euro overnight rate, not the US rate."],
      };
    }
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/portfolio/library", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as { lines: { id: string }[] };
    body.lines = body.lines.map((line) => (line.id === "fi_na_gov" ? { ...line, hedge_eur: true } : line));
    await route.fulfill({ response, json: body });
  });
  return asked;
}

test("switch to EUR: the request, the header pill, the credits, the remembered choice and the hedge badge", async ({ page }) => {
  const asked = await euroBackend(page);

  await page.goto("/?t=SYN&range=3Y");
  await expect(page.locator(".abar")).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.locator(".ccy-pill")).toHaveCount(0);
  const currency = page.getByRole("radiogroup", { name: "Currency" });
  await expect(currency.getByRole("radio", { name: "USD" })).toBeChecked();

  // The switch reruns the report with ccy=EUR and shows the euro view.
  await currency.getByRole("radio", { name: "EUR" }).check();
  await expect(page).toHaveURL(/[?&]ccy=EUR\b/);
  await expect(page.locator(".ccy-pill")).toHaveText("Figures in EUR", { timeout: FIRST_REPORT_MS });
  expect(asked.length).toBeGreaterThan(0);
  await expect(page.locator("#summary .cur-notes")).toContainText("Cash earns the euro overnight rate");
  await expect(page.locator("footer.colophon")).toContainText("Exchange rates: European Central Bank, euro foreign exchange reference rates.");
  await expect(page.locator("footer.colophon")).toContainText("Euro short-term rate and EONIA: European Central Bank, ECB Data Portal.");

  // The choice is remembered: a URL without ccy opens in EUR, and ccy=USD in the URL wins over it.
  await page.goto("/?t=SYN&range=3Y");
  await expect(page.getByRole("radiogroup", { name: "Currency" }).getByRole("radio", { name: "EUR" })).toBeChecked();
  await expect(page.locator(".ccy-pill")).toHaveText("Figures in EUR", { timeout: FIRST_REPORT_MS });
  await page.goto("/?t=SYN&range=3Y&ccy=USD");
  await expect(page.getByRole("radiogroup", { name: "Currency" }).getByRole("radio", { name: "USD" })).toBeChecked();
  await expect(page.locator(".abar")).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.locator(".ccy-pill")).toHaveCount(0);

  // The composer shows the hedge badge on a bond line in the euro view only.
  await page.goto("/?m=portfolio&ccy=EUR");
  await page.getByLabel("Name", { exact: true }).fill("Euro 60/40");
  await page.getByRole("radio", { name: /^60\/40/ }).check();
  await page.getByRole("button", { name: "Create portfolio" }).click();
  const bonds = page.locator(".tree-panel .t-row", { hasText: "N. American Government Bonds" });
  await expect(bonds.getByText("hedged to EUR")).toBeVisible();
  await page.getByRole("radiogroup", { name: "Currency" }).getByRole("radio", { name: "USD" }).check();
  await expect(page.getByText("hedged to EUR")).toHaveCount(0);
});
