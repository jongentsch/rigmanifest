import { expect, test } from "@playwright/test";

test("matches the Dark Modern Workshop baseline", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) memory plan" }),
  ).toBeVisible();

  await expect(page).toHaveScreenshot("modern-workshop-dark.png");
});

test("matches the Light Modern Workshop baseline", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Color theme").selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await expect(page).toHaveScreenshot("modern-workshop-light.png");
});
