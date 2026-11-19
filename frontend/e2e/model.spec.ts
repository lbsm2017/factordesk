import { expect, test } from "@playwright/test";

const FIRST_REPORT_MS = 120_000;

test("the dashboard opens on FF6 without a model control, and model=ff5 in the URL still opens FF5", async ({ page }) => {
  await page.goto("/?t=SYN&range=3Y");
  const strip = page.locator("#alpha-strip");
  await expect(strip).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(strip.locator("tbody tr")).toHaveCount(4);
  await expect(strip).toContainText("A higher R² does not make a model more correct. Alpha depends on the model.");
  // No model in the URL means FF6, and the URL stays as typed. No control shows the model.
  await expect(page.getByRole("group", { name: "Factor model" })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "FF6" })).toHaveCount(0);
  await expect(page).not.toHaveURL(/model=/);
  await expect(page.locator("#exposures")).toContainText("Mom");
  await expect(page.locator("#kalman")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Download/ })).toHaveAttribute("href", /model=ff6/);

  await page.goto("/?t=SYN&range=3Y&model=ff5");
  await expect(strip).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.getByRole("group", { name: "Factor model" })).toHaveCount(0);
  await expect(page.locator("#exposures")).not.toContainText("Mom", { timeout: FIRST_REPORT_MS });
  await expect(strip.locator("tbody tr")).toHaveCount(4);
  await expect(page.getByRole("link", { name: /Download/ })).toHaveAttribute("href", /model=ff5/);
});

test("an old URL with explicit range and model keeps its meaning", async ({ page }) => {
  await page.goto("/?t=SYN&range=3Y&model=ff5");
  await expect(page.locator("#alpha-strip")).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.getByRole("radio", { name: "3Y" })).toBeChecked();
  await expect(page).toHaveURL(/[?&]range=3Y\b.*[?&]model=ff5\b/);
  await expect(page.locator("#exposures")).not.toContainText("Mom");
});

test("a ticker alone opens on 10Y and FF6", async ({ page }) => {
  await page.goto("/?t=SYN");
  await expect(page.locator("#alpha-strip")).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(page.getByRole("radio", { name: "10Y" })).toBeChecked();
  await expect(page.getByRole("radio", { name: "FF6" })).toHaveCount(0);
  expect(new URL(page.url()).search).toBe("?t=SYN");
});
