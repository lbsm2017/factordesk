import { expect, test } from "@playwright/test";

/** A month-end date, from January 2015. */
function monthEnd(index: number): string {
  const d = new Date(Date.UTC(2015, index + 1, 0));
  return d.toISOString().slice(0, 10);
}

/** 84 monthly returns (January 2015 to December 2021) from a fixed generator: the same file on every run. */
function record(months: number, skip: number | null = null): Buffer {
  let seed = 12345;
  const rows = ["date,return"];
  for (let i = 0; i < months; i++) {
    seed = (seed * 1103515245 + 12345) % 2 ** 31;
    if (i === skip) continue;
    rows.push(`${monthEnd(i)},${(seed / 2 ** 31 - 0.5) * 0.12}`);
  }
  return Buffer.from(`${rows.join("\n")}\n`);
}

test("track record upload on the fake backend", async ({ page }) => {
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

  // No mode in the URL means the ticker mode; the old landing page is unchanged.
  await page.goto("/");
  await expect(page.getByRole("radio", { name: "Ticker" })).toBeChecked();
  await expect(page.getByRole("combobox", { name: "Ticker" })).toBeVisible();

  // The switch gives m=track and the drop zone.
  await page.getByRole("radio", { name: "Track record" }).check();
  await expect(page).toHaveURL(/[?&]m=track\b/);
  await expect(page.getByTestId("track-landing")).toBeVisible();

  // A file with a missing month is refused with the server's message.
  const file = page.locator("input[type=file]");
  await file.setInputFiles({ name: "gap.csv", mimeType: "text/csv", buffer: record(84, 20) });
  await page.getByRole("button", { name: "Factor it" }).click();
  const refused = page.getByTestId("report-error");
  await expect(refused).toBeVisible();
  await expect(refused).toContainText("months must be consecutive");

  // A good file gives the report on the existing layout: months, no daily-only panels.
  await file.setInputFiles({ name: "fund.csv", mimeType: "text/csv", buffer: record(84) });
  await page.getByLabel("Name").fill("Example Fund");
  await page.getByRole("radio", { name: "Net" }).check();
  await page.getByRole("button", { name: "Factor it" }).click();
  const bar = page.locator(".abar");
  await expect(bar).toBeVisible({ timeout: 120_000 });
  await expect(page.locator("#header h1")).toContainText("Example Fund");
  await expect(page.locator("#header")).toContainText("Uploaded track record, returns after fees");
  await expect(bar).toContainText("84 months");
  await expect(bar).not.toContainText("trading day");
  await expect(page.locator("#summary")).toContainText("Alpha (annual)");
  await expect(page.locator("#exposures")).toBeVisible();
  for (const gone of ["#rolling", "#world-beta", "#lead-lag", "#fragility", "#kalman", "#shrunk"]) {
    await expect(page.locator(gone)).toHaveCount(0);
  }
  await expect(page.getByRole("link", { name: "Download report" })).toHaveCount(0);
  // The record is kept out of the URL and the browser storage.
  expect(page.url()).not.toContain("Example");
  expect(await page.evaluate(() => JSON.stringify(window.localStorage))).not.toContain("Example");

  // Back to the ticker mode.
  await page.getByRole("radio", { name: "Ticker" }).check();
  await expect(page).not.toHaveURL(/[?&]m=track\b/);
  await expect(page.getByRole("combobox", { name: "Ticker" })).toBeVisible();

  expect(foreign, "requests to a host other than 127.0.0.1").toEqual([]);
});
