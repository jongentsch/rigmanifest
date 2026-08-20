import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("has no detectable accessibility violations", async ({ page }) => {
  await page.goto("/compile");
  await page.getByRole("button", { name: "Compile plan" }).click();
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) compiled plan" }),
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

test("image-backed radio inventory has no detectable accessibility violations", async ({ page }) => {
  await page.goto("/radios");
  await expect(page.getByRole("heading", { name: "My radios" })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("profile editor has no detectable accessibility violations", async ({ page }) => {
  await page.goto("/profiles");
  await expect(page.getByRole("heading", { name: "Profiles", exact: true })).toBeVisible();
  await expect(page.getByLabel("Selected set order")).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("update settings have no detectable accessibility violations", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
