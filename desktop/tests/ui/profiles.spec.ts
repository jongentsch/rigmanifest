import { expect, test } from "@playwright/test";

test("previews selected sets as banks and keeps standalone additions unassigned", async ({ page }) => {
  await page.goto("/profiles");

  const preview = page.getByRole("region", { name: "Prospective banks" });
  const homeBank = preview.getByRole("region", { name: "Home essentials frequency group" });
  const weatherBank = preview.getByRole("region", { name: "US NOAA Weather Broadcasts frequency group" });
  await expect(homeBank).toContainText("Bank from set");
  await expect(homeBank).toContainText("2m Calling");
  await expect(homeBank).toContainText("146.520000 MHz");
  await expect(homeBank).toContainText("-0.600 MHz");
  await expect(homeBank).toContainText("CTCSS 100.0 Hz");
  await expect(homeBank).toContainText("Default");
  await expect(homeBank).toContainText("Scan");
  await expect(weatherBank).toContainText("NOAA Weather 1");

  await page.getByRole("checkbox", { name: /^NOAA Weather 1 / }).check();
  await page.getByRole("checkbox", { name: /US NOAA Weather Broadcasts/ }).uncheck();

  const additions = preview.getByRole("region", { name: "Individual definitions frequency group" });
  await expect(additions).toContainText("Unassigned additions");
  await expect(additions).toContainText("NOAA Weather 1");
  await expect(weatherBank).toHaveCount(0);
});

test("reorders selected profile sets by dragging", async ({ page }) => {
  await page.goto("/profiles");

  const selectedOrder = page.getByLabel("Selected set order");
  const rows = selectedOrder.locator(".selected-set-order-row");
  await expect(rows.nth(0)).toContainText("Home essentials");
  await expect(rows.nth(1)).toContainText("US NOAA Weather Broadcasts");

  const source = page.getByRole("button", {
    name: /Reorder US NOAA Weather Broadcasts/,
  });
  const target = page.getByRole("button", { name: /Reorder Home essentials/ });
  await source.dragTo(target, { targetPosition: { x: 4, y: 2 } });

  await expect(rows.nth(0)).toContainText("US NOAA Weather Broadcasts");
  await expect(rows.nth(1)).toContainText("Home essentials");
  await expect(page.getByRole("status")).toContainText("Profiles saved");

  await page.reload();
  await expect(selectedOrder.locator(".selected-set-order-row").nth(0)).toContainText(
    "US NOAA Weather Broadcasts",
  );
  const previewGroups = page
    .getByRole("region", { name: "Prospective banks" })
    .locator(".profile-bank-group");
  await expect(previewGroups.nth(0)).toContainText("US NOAA Weather Broadcasts");
  await expect(previewGroups.nth(1)).toContainText("Home essentials");
});

test("persists reusable profile composition and submits multiple profiles", async ({ page }) => {
  await page.goto("/profiles");
  await page.getByRole("button", { name: "Add profile" }).click();

  const name = page.getByLabel("Profile name");
  await name.fill("Vacation");
  await name.press("Tab");
  await page.getByLabel("Advisory band plan").selectOption(
    "southern-nevada-repeater-council",
  );
  await page.getByRole("checkbox", { name: /Home essentials/ }).check();
  await page.getByRole("checkbox", { name: /^NOAA Weather 1 / }).check();
  await expect(page.getByRole("status")).toContainText("Profiles saved");

  await page.reload();
  await page.getByRole("button", { name: /Vacation/ }).click();
  await expect(page.getByLabel("Profile name")).toHaveValue("Vacation");
  await expect(page.getByLabel("Advisory band plan")).toHaveValue(
    "southern-nevada-repeater-council",
  );
  await expect(page.getByRole("checkbox", { name: /Home essentials/ })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: /^NOAA Weather 1 / })).toBeChecked();

  await page.getByRole("link", { name: "Compile & export" }).click();
  await page.getByRole("checkbox", { name: /Vacation/ }).check();
  await page.getByRole("button", { name: "Compile plan" }).click();
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) compiled plan" }),
  ).toBeVisible();

  const calls = await page.evaluate(() =>
    (
      window as typeof window & {
        __RIGMANIFEST_UI_TEST_CALLS__?: Array<Record<string, unknown>>;
      }
    ).__RIGMANIFEST_UI_TEST_CALLS__,
  );
  expect(calls?.filter((item) => item.method === "compileSelection").at(-1)).toMatchObject({
    profile: expect.stringMatching(/^home,profile-/),
    profiles: [
      expect.objectContaining({ id: "home" }),
      expect.objectContaining({
        name: "Vacation",
        frequency_set_ids: ["home-essentials"],
        frequency_definition_ids: ["us-noaa-weather-1"],
        frequency_plan_id: "southern-nevada-repeater-council",
      }),
    ],
  });
});
