import { expect, test } from "@playwright/test";

const FIRST_REPORT_MS = 120_000;

test("model toggle switches between FF5 and FF6 on the fake backend", async ({ page }) => {
  await page.goto("/?t=SYN&range=3Y");
  const strip = page.locator("#alpha-strip");
  await expect(strip).toBeVisible({ timeout: FIRST_REPORT_MS });
  await expect(strip.locator("tbody tr")).toHaveCount(4);
  await expect(strip).toContainText("A higher R² does not make a model more correct. Alpha depends on the model.");
  await expect(page.getByRole("radio", { name: "FF5" })).toBeChecked();
  await expect(page.locator("#exposures")).not.toContainText("Mom");

  const toggle = page.getByRole("group", { name: "Factor model" });
  await toggle.getByRole("radio", { name: "FF6" }).check();
  await expect(page).toHaveURL(/[?&]model=ff6\b/);
  await expect(page.locator("#exposures")).toContainText("Mom", { timeout: FIRST_REPORT_MS });
  await expect(page.locator("#kalman")).toHaveCount(0);
  await expect(strip.locator("tbody tr")).toHaveCount(4);
  await expect(page.getByRole("link", { name: /Download/ })).toHaveAttribute("href", /model=ff6/);

  await toggle.getByRole("radio", { name: "FF5" }).check();
  await expect(page).not.toHaveURL(/model=/);
  await expect(page.locator("#exposures")).not.toContainText("Mom");
});
