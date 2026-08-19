import { expect, test } from "@playwright/test";

test("update settings check GitHub automatically and persist the preference", async ({ page }) => {
  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByText("Development build", { exact: true })).toBeVisible();
  await expect(page.getByText("You have the latest published version.")).toBeVisible();

  const automaticChecks = page.getByRole("checkbox", { name: "Check automatically" });
  await expect(automaticChecks).toBeChecked();
  await automaticChecks.uncheck();
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Check automatically" })).not.toBeChecked();

  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(page.getByText("You have the latest published version.")).toBeVisible();
});
