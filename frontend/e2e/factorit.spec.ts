import { expect, test } from "@playwright/test";

const FIRST_REPORT_MS = 120_000;

// A range no other spec asks for, so the report is computed (not cached) and its steps are streamed.
const FRESH = "/?t=SYN&start=2017-03-01&end=2019-06-01";

test("Factor it shows the steps of the run, then opens the report", async ({ page }) => {
  await page.goto(FRESH);
  const card = page.getByTestId("run-card");
  await expect(card.getByRole("heading", { name: "Building the report for SYN" })).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(card.getByText("Downloading prices")).toBeVisible();
  // The button is busy and keeps its place; the placeholder panels have their real titles.
  await expect(page.getByRole("button", { name: "Factoring…" })).toHaveAttribute("aria-disabled", "true");
  await expect(page.locator("section.ph-panel h2").first()).toHaveText("Price");
  // Nothing in the section list yet: the placeholders have no ids.
  await expect(page.locator("#summary")).toHaveCount(0);

  await expect(page.locator(".abar")).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.locator("#summary")).toContainText("Alpha (annual)");
  await expect(page.getByTestId("run-card")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Factor it" })).toBeVisible();
  await expect(page.getByTestId("run-status")).toHaveText("The report for SYN is ready.");
});

test("a run that fails shows the step that stopped, and Change ticker moves focus to the field", async ({ page }) => {
  await page.goto("/?t=SYN&start=2018-01-02&end=2018-03-01");
  const failed = page.getByTestId("report-error");
  await expect(failed).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(failed).toContainText("at least 504");
  await expect(failed.getByRole("heading", { name: "The report for SYN stopped" })).toBeVisible();
  await expect(failed.locator("li[data-state='failed']")).toHaveCount(1);
  await expect(failed.locator("li[data-state='not-run']")).not.toHaveCount(0);
  await expect(failed.getByRole("alert")).toBeFocused();
  await failed.getByRole("button", { name: "Change ticker" }).click();
  await expect(page.getByRole("combobox", { name: "Ticker" })).toBeFocused();
});

test("a re-run keeps the old report dimmed and names the new request", async ({ page }) => {
  await page.goto("/?t=SYN&range=3Y");
  await expect(page.locator(".abar")).toBeVisible({ timeout: FIRST_REPORT_MS });
  await page.getByRole("radio", { name: "Full history" }).check();
  await expect(page.getByTestId("rerun-chip")).toContainText("Updating SYN", { timeout: FIRST_REPORT_MS });
  await expect(page.locator(".report-region.dim")).toHaveAttribute("inert", "");
  await expect(page.getByTestId("run-card")).toHaveCount(0);
  await expect(page.getByTestId("rerun-chip")).toHaveCount(0, { timeout: FIRST_REPORT_MS });
  await expect(page.locator(".report-region.dim")).toHaveCount(0);
});
