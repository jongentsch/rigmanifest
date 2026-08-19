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

test("scales all interface text and persists the preference", async ({ page }) => {
  await page.goto("/settings");

  const scale = page.getByLabel("Text scale");
  const updateDetail = page.getByText(/Check at startup at most once every 24 hours/);
  const initialSize = await updateDetail.evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).fontSize),
  );

  await scale.selectOption("1.3");
  await expect(page.locator("html")).toHaveAttribute("data-text-scale", "1.3");
  const scaledSize = await updateDetail.evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).fontSize),
  );
  expect(scaledSize).toBeCloseTo(initialSize * 1.3, 1);

  await page.reload();
  await expect(page.getByLabel("Text scale")).toHaveValue("1.3");
  await expect(page.locator("html")).toHaveCSS("font-size", "20.8px");
});
