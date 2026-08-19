import { expect, test } from "@playwright/test";

test("defaults to Dark and persists a Light preference", async ({ page }) => {
  await page.goto("/");

  const appearance = page.getByLabel("Color theme");
  await expect(appearance).toHaveValue("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await appearance.selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.reload();
  await expect(page.getByLabel("Color theme")).toHaveValue("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("System mode responds to operating-system color changes", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.getByLabel("Color theme").selectOption("system");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
