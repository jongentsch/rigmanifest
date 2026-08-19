import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("has no detectable accessibility violations", async ({ page }) => {
  await page.goto("/compile");
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) memory plan" }),
  ).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("frequency catalog editor has no detectable accessibility violations", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("heading", { name: "Frequency library" })).toBeVisible();
  await page.getByRole("button", { name: "New definition" }).click();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
