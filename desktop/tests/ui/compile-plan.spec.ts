import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/compile");
  await page.getByRole("button", { name: "Compile plan" }).click();
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) memory plan" }),
  ).toBeVisible();
});

test("compiles selected sets for the image-backed radio", async ({ page }) => {
  const summary = page.getByLabel("Compilation summary");
  await expect(summary).toContainText("3Programmed");
  await expect(summary).toContainText("0Factory-provided");
  await expect(summary).toContainText("0Omitted");
  await expect(summary).toContainText("3Warnings");
  await expect(summary).toContainText("0Errors");

  await expect(page.getByRole("row", { name: /01 2M CAL/ })).toContainText(
    "146.520000 MHz",
  );
  await expect(page.getByRole("row", { name: /02 2M LOC/ })).toContainText(
    "-0.600 MHz",
  );
  await expect(page.getByRole("row", { name: /03 70CM L/ })).toContainText(
    "+5.000 MHz",
  );

  await expect(page.getByText("US NOAA Weather Broadcasts").first()).toBeVisible();
  await expect(page.getByText("FACTORY_SET_AVAILABLE")).toHaveCount(0);
  await expect(page.getByText("TX_DISABLE_NOT_REPRESENTABLE")).toHaveCount(0);
});

test("recompiles and exports through the UI-test adapter", async ({ page }) => {
  await page.getByRole("button", { name: "Export CHIRP IMG" }).click();

  await expect(page.getByRole("status")).toContainText(
    "/exports/home-default-vx6r.img",
  );

  const calls = await page.evaluate(() =>
    (
      window as typeof window & {
        __RIGMANIFEST_UI_TEST_CALLS__?: Array<Record<string, unknown>>;
      }
    ).__RIGMANIFEST_UI_TEST_CALLS__,
  );

  expect(calls).toContainEqual({
    method: "chooseImageOutputPath",
    profile: "home",
    target: "default-vx6r",
  });
  expect(calls).toContainEqual(expect.objectContaining({
    method: "compileSelection",
    profile: "home",
    target: "default-vx6r",
    outputPath: "/exports/home-default-vx6r.img",
    configuration: {
      memoryStart: 1,
      mapSetsToBanks: true,
      useFactorySets: false,
      additionalFrequencySetIds: [],
      additionalFrequencyDefinitionIds: [],
      advisoryPlanId: "arrl-us-national",
    },
  }));

  await page.getByRole("link", { name: "My radios" }).click();
  await expect(page.locator(".image-version")).toHaveCount(2);
  await expect(page.locator(".image-version").first()).toContainText("Compiled");
  await expect(page.locator(".image-version").first()).toContainText(
    "home-default-vx6r.img",
  );
});

test("keeps profiles, the frequency library, and radio inventory on separate pages", async ({ page }) => {
  await page.getByRole("link", { name: "Profiles" }).click();
  await expect(page.getByRole("heading", { name: "Profiles", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Home" })).toBeVisible();

  await page.getByRole("link", { name: "Frequency library" }).click();
  await expect(page.getByRole("heading", { name: "Frequency library" })).toBeVisible();
  await page.getByRole("button", { name: /US NOAA Weather Broadcasts/ }).click();
  await expect(page.getByRole("row", { name: /WX1 NOAA Weather 1/ })).toBeVisible();

  await page.getByRole("link", { name: "My radios" }).click();
  await expect(page.getByRole("heading", { name: "My radios" })).toBeVisible();
  await expect(page.getByLabel("Source image")).toHaveValue("Yaesu_VX-6.img");
  await expect(page.locator(".model-facts")).toContainText("24");
});
