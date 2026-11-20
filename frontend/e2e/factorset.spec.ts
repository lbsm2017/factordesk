import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const FIRST_REPORT_MS = 120_000;
const SHOTS = "C:/Users/loren/Research/factordesk-wt/fs-shots";

/**
 * The fake backend has no Europe factors and no exchange rates. The Europe and euro views are tested
 * by answering with the fake backend's own USD answer plus the fields the real backend adds
 * (`factor_set` and `currency` on the report). The parameters the fake backend cannot serve are
 * taken off the request it sees, and recorded so the test can check what the page asked for.
 */
async function europeBackend(page: Page): Promise<string[]> {
  const asked: string[] = [];
  const plain = (url: string): string => {
    const u = new URL(url);
    u.searchParams.delete("ccy");
    u.searchParams.delete("factor_set");
    return u.toString();
  };
  // No progress stream here: the page falls back to the plain endpoint, which is answered below.
  await page.route(/\/api\/report\/SYN\/stream\?/, (route) =>
    route.fulfill({ status: 404, json: { code: "not_found", message: "Not found.", action: "Check the address." } }),
  );
  await page.route(/\/api\/report\/SYN\/ranges/, async (route) => {
    const url = route.request().url();
    if (new URL(url).searchParams.get("factor_set") === "europe") asked.push(url);
    await route.continue({ url: plain(url) });
  });
  await page.route(/\/api\/report\/SYN\?/, async (route) => {
    const url = route.request().url();
    const params = new URL(url).searchParams;
    const response = await route.fetch({ url: plain(url) });
    const body = (await response.json()) as Record<string, unknown>;
    if (params.get("factor_set") === "europe") {
      asked.push(url);
      body["factor_set"] = "europe";
    }
    if (params.get("ccy") === "EUR") {
      body["currency"] = {
        reference: "EUR",
        fx_source: "Exchange rates: European Central Bank, euro foreign exchange reference rates.",
        rate_source: "Euro short-term rate and EONIA: European Central Bank, ECB Data Portal.",
        notes: ["Cash earns the euro overnight rate, not the US rate."],
      };
    }
    await route.fulfill({ response, json: body });
  });
  return asked;
}

test("the factor set: the switch, fs=europe, the request, the header pill and the Europe note", async ({ page }) => {
  const asked = await europeBackend(page);
  await page.goto("/?t=SYN&range=3Y");
  await expect(page.locator(".abar")).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.locator(".set-pill")).toHaveText("US factors");
  const set = page.getByRole("radiogroup", { name: "Factor set" });
  await expect(set.getByRole("radio", { name: "US" })).toBeChecked();

  await set.getByRole("radio", { name: "Europe" }).check();
  await expect(page).toHaveURL(/[?&]fs=europe\b/);
  await expect(page.locator(".set-pill")).toHaveText("Europe factors", { timeout: FIRST_REPORT_MS });
  expect(asked.some((u) => u.includes("/api/report/SYN?") && u.includes("factor_set=europe"))).toBe(true);
  await expect(page.locator("#summary .cur-notes")).toContainText("Developed Europe");

  // A shared link keeps the set; the US choice takes the parameter out again.
  await page.goto("/?t=SYN&range=3Y&fs=europe");
  await expect(set.getByRole("radio", { name: "Europe" })).toBeChecked();
  await set.getByRole("radio", { name: "US" }).check();
  await expect(page).not.toHaveURL(/fs=/);
});

test("What EUR changes: opens from the link, traps focus, closes with Escape and returns focus", async ({ page }) => {
  await europeBackend(page);
  await page.goto("/?t=SYN&range=3Y&ccy=EUR");
  const link = page.getByRole("button", { name: "What EUR changes" });
  await expect(link).toBeVisible({ timeout: FIRST_REPORT_MS });
  await link.click();
  const dialog = page.getByRole("dialog", { name: "What EUR changes" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "Close" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(link).toBeFocused();
});

test("the EUR and Europe header and the open panel @shots", async ({ page }) => {
  await europeBackend(page);
  await page.goto("/?t=SYN&range=3Y&ccy=EUR&fs=europe");
  await expect(page.locator(".set-pill")).toHaveText("Europe factors", { timeout: FIRST_REPORT_MS });
  await expect(page.locator(".ccy-pill")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/europe-eur-header.png`, clip: { x: 0, y: 0, width: 1440, height: 560 } });
  await page.getByRole("button", { name: "What EUR changes" }).click();
  await expect(page.getByRole("dialog", { name: "What EUR changes" })).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/what-eur-changes-dialog.png` });
});
