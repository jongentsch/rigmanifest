import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) memory plan" }),
  ).toBeVisible();
});

test("renders the deterministic Home compilation result", async ({ page }) => {
  const summary = page.getByLabel("Compilation summary");
  await expect(summary).toContainText("3Included");
  await expect(summary).toContainText("1Omitted");
  await expect(summary).toContainText("3Warnings");
  await expect(summary).toContainText("1Errors");

  await expect(page.getByRole("row", { name: /01 2M CAL/ })).toContainText(
    "146.520000 MHz",
  );
  await expect(page.getByRole("row", { name: /02 2M LOC/ })).toContainText(
    "-0.600 MHz",
  );
  await expect(page.getByRole("row", { name: /03 70CM L/ })).toContainText(
    "+5.000 MHz",
  );

  await expect(page.getByText("TX_DISABLE_NOT_REPRESENTABLE")).toBeVisible();
  await expect(page.getByRole("row", { name: /Omitted NOAA Weather 1/ })).toContainText(
    "Disabled",
  );
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
  expect(calls).toContainEqual({
    method: "compileProfile",
    profile: "home",
    target: "yaesu-vx6r",
    outputPath: "/exports/home-yaesu-vx6r.csv",
  });
});
