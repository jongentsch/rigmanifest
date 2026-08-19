import { expect, test } from "@playwright/test";

test("creates, persists, and submits user-owned frequency records", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("heading", { name: "Frequency library" })).toBeVisible();

  await page.getByRole("button", { name: "Add set" }).click();
  const setName = page.getByLabel("Set name");
  await setName.fill("Field day");
  await setName.press("Tab");

  await page.getByRole("button", { name: "New definition" }).click();
  const definitionName = page.getByLabel("Name", { exact: true });
  await definitionName.fill("Field simplex");
  await definitionName.press("Tab");
  const receive = page.getByLabel("Receive MHz");
  await receive.fill("146.550000");
  await receive.press("Tab");
  await expect(page.getByRole("status")).toContainText("Catalog saved");

  await page.reload();
  await page.getByRole("button", { name: /Field day/ }).click();
  await expect(page.getByRole("row", { name: /Field simplex/ })).toContainText(
    "146.550000 MHz",
  );

  await page.getByRole("link", { name: "Compile & export" }).click();
  const customSet = page.getByRole("checkbox", { name: /Field day/ });
  await expect(customSet).toBeVisible();
  await customSet.check();
  await page.getByRole("button", { name: "Compile plan" }).click();

  const calls = await page.evaluate(() =>
    (
      window as typeof window & {
        __RIGMANIFEST_UI_TEST_CALLS__?: Array<Record<string, unknown>>;
      }
    ).__RIGMANIFEST_UI_TEST_CALLS__,
  );
  const compileCall = calls?.filter((item) => item.method === "compileProfile").at(-1);
  expect(compileCall).toMatchObject({
    configuration: {
      frequencySetIds: expect.arrayContaining([
        "home-essentials",
        "us-noaa-weather",
      ]),
    },
    userCatalog: {
      frequencyDefinitions: expect.arrayContaining([
        expect.objectContaining({
          name: "Field simplex",
          receive_frequency_hz: 146_550_000,
          origin: "user",
        }),
      ]),
      frequencySets: expect.arrayContaining([
        expect.objectContaining({ name: "Field day", origin: "user" }),
      ]),
    },
  });
});
