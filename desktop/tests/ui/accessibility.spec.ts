import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("has no detectable accessibility violations", async ({ page }) => {
  await page.goto("/compile");
  await page.getByRole("button", { name: "Compile plan" }).click();
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

test("radio model search has no detectable accessibility violations", async ({ page }) => {
  await page.goto("/radios");
  await expect(page.getByRole("heading", { name: "My radios" })).toBeVisible();
  await page.getByLabel("Find manufacturer or model").fill("quansheng");

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
