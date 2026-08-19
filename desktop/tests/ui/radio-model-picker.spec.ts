import { expect, test } from "@playwright/test";

test("adds a radio by detecting its CHIRP image", async ({ page }) => {
  await page.goto("/radios");
  await expect(page.getByRole("heading", { name: "My radios" })).toBeVisible();

  await page.getByRole("button", { name: "Add radio from IMG" }).first().click();

  await expect(page.getByLabel("Detected model")).toHaveValue("Yaesu VX-6");
  await expect(page.getByLabel("Source image")).toHaveValue("Yaesu_VX-6.img");
  await expect(page.locator(".model-facts")).toContainText("999");
  await expect(page.locator(".model-facts")).toContainText("24");
  await expect(page.locator(".model-facts")).toContainText("124");
  await expect(page.getByRole("heading", { name: "Radio image versions" })).toBeVisible();
  await expect(page.getByText("Imported source")).toBeVisible();
  await expect(page.locator(".image-version")).toContainText("Yaesu_VX-6.img");

  const calls = await page.evaluate(() => window.__RIGMANIFEST_UI_TEST_CALLS__);
  expect(calls).toContainEqual(expect.objectContaining({
    method: "importChirpImage",
    profile: "/imports/Yaesu_VX-6.img",
  }));
});

test("persists the user-facing name without changing detected model facts", async ({ page }) => {
  await page.goto("/radios");
  await page.getByLabel("Radio name").fill("Trail handheld");
  await page.getByRole("button", { name: "Save radio" }).click();

  await page.reload();

  await expect(page.getByLabel("Radio name")).toHaveValue("Trail handheld");
  await expect(page.getByLabel("Detected model")).toHaveValue("Yaesu VX-6");
});
