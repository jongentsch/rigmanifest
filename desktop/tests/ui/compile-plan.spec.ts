import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/compile");
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) memory plan" }),
  ).toBeVisible();
});

test("compiles selected sets and separates factory coverage", async ({ page }) => {
  const summary = page.getByLabel("Compilation summary");
  await expect(summary).toContainText("3Programmed");
  await expect(summary).toContainText("10Factory-provided");
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
  await expect(page.getByText("FACTORY_SET_AVAILABLE")).toBeVisible();
  await expect(page.getByText("TX_DISABLE_NOT_REPRESENTABLE")).toHaveCount(0);
});

test("recompiles and exports through the UI-test adapter", async ({ page }) => {
  await page.getByRole("button", { name: "Compile plan" }).click();
  await page.getByRole("button", { name: "Export CHIRP CSV" }).click();

  await expect(page.getByRole("status")).toContainText(
    "/exports/home-yaesu-vx6r.csv",
  );

  const calls = await page.evaluate(() =>
    (
      window as typeof window & {
        __RIGMANIFEST_UI_TEST_CALLS__?: Array<Record<string, unknown>>;
      }
    ).__RIGMANIFEST_UI_TEST_CALLS__,
  );

  expect(calls).toContainEqual({
    method: "chooseCsvOutputPath",
    profile: "home",
    target: "yaesu-vx6r",
  });
  expect(calls).toContainEqual(expect.objectContaining({
    method: "compileProfile",
    profile: "home",
    target: "yaesu-vx6r",
    outputPath: "/exports/home-yaesu-vx6r.csv",
    configuration: {
      memoryStart: 1,
      mapSetsToBanks: true,
      useFactorySets: true,
      frequencySetIds: ["home-essentials", "us-noaa-weather"],
    },
  }));
});

test("keeps the frequency library and radio inventory on separate pages", async ({ page }) => {
  await page.getByRole("link", { name: "Frequency library" }).click();
  await expect(page.getByRole("heading", { name: "Frequency library" })).toBeVisible();
  await page.getByRole("button", { name: /US NOAA Weather Broadcasts/ }).click();
  await expect(page.getByRole("row", { name: /WX1 NOAA Weather 1/ })).toBeVisible();

  await page.getByRole("link", { name: "My radios" }).click();
  await expect(page.getByRole("heading", { name: "My radios" })).toBeVisible();
  await expect(page.getByText("US NOAA Weather Broadcasts")).toBeVisible();
  await expect(page.getByText("CHIRP editing")).toBeVisible();
});
