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
  await page.getByLabel("Transmit access").selectOption("ctcss");
  await page.getByLabel("Transmit CTCSS Hz").fill("123.0");
  await page.getByLabel("Transmit CTCSS Hz").press("Tab");
  await page.getByLabel("Receive squelch").selectOption("dcs");
  await page.getByLabel("Receive DCS code").fill("25");
  await page.getByLabel("Receive DCS code").press("Tab");
  await page.getByLabel("Receive DCS polarity").selectOption("R");
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
          transmit_access: expect.objectContaining({
            kind: "ctcss",
            ctcss_hz: 123,
          }),
          receive_squelch: expect.objectContaining({
            kind: "dcs",
            dcs_code: 25,
            dcs_polarity: "R",
          }),
        }),
      ]),
      frequencySets: expect.arrayContaining([
        expect.objectContaining({ name: "Field day", origin: "user" }),
      ]),
    },
  });
});

test("migrates the legacy combined tone record without losing user data", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "rigmanifest.user-catalog.v1",
      JSON.stringify({
        frequencyDefinitions: [
          {
            id: "legacy-repeater",
            name: "Legacy repeater",
            origin: "user",
            read_only: false,
            receive_frequency_hz: 146_910_000,
            transmit_behavior: "offset",
            transmit_frequency_hz: null,
            offset_hz: -600_000,
            mode: "FM",
            tone: {
              mode: "tsql",
              encode_hz: 100,
              decode_hz: 123,
              dtcs_code: null,
              dtcs_polarity: "NN",
            },
            tags: [],
            priority: "normal",
            notes: "kept through migration",
          },
        ],
        frequencySets: [
          {
            id: "legacy-set",
            name: "Legacy set",
            origin: "user",
            read_only: false,
            description: "",
            members: [
              {
                frequency_definition_id: "legacy-repeater",
                position: 0,
                channel_designator: null,
              },
            ],
          },
        ],
      }),
    );
  });

  await page.goto("/library");

  await expect(page.getByRole("heading", { name: "Legacy repeater" })).toBeVisible();
  await expect(page.getByLabel("Transmit access")).toHaveValue("ctcss");
  await expect(page.getByLabel("Transmit CTCSS Hz")).toHaveValue("100");
  await expect(page.getByLabel("Receive squelch")).toHaveValue("ctcss");
  await expect(page.getByLabel("Receive CTCSS Hz")).toHaveValue("123");
  await expect(page.getByLabel("Notes")).toHaveValue("kept through migration");

  const migrated = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("rigmanifest.user-catalog.v2") ?? "null"),
  );
  expect(migrated.frequencyDefinitions[0]).not.toHaveProperty("tone");
});

test("shows sourced plan advice and only applies an offset on request", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("heading", { name: "Frequency library" })).toBeVisible();

  const receive = page.getByLabel("Receive MHz");
  await receive.fill("147.300000");
  await receive.press("Tab");

  const suggestion = page.getByLabel("Frequency plan suggestion");
  await expect(suggestion).toContainText("2 m repeater outputs (147 MHz)");
  await expect(suggestion).toContainText("Suggested offset +0.600 MHz");
  await expect(suggestion.getByRole("link", { name: "View source" })).toHaveAttribute(
    "href",
    "https://www.arrl.org/band-plan",
  );
  await expect(page.getByLabel("Transmit behavior")).toHaveValue("same");

  await suggestion.getByRole("button", { name: "Use suggested offset" }).click();

  await expect(page.getByLabel("Transmit behavior")).toHaveValue("offset");
  await expect(page.getByLabel("Offset MHz")).toHaveValue("0.6");
  await expect(suggestion.getByRole("button", { name: "Offset applied" })).toBeDisabled();

  await receive.fill("927.138000");
  await receive.press("Tab");
  await expect(suggestion).toContainText("33 cm repeater outputs");
  await expect(suggestion).toContainText("12.5 kHz raster: off raster");
});

test("imports a CHIRP CSV into reusable definitions and a set", async ({ page }) => {
  await page.goto("/library");

  await page.getByRole("button", { name: "Import CHIRP CSV" }).click();

  await expect(page.getByRole("status")).toContainText(
    "Imported 1 frequency definitions into Imported road-trip",
  );
  await expect(page.getByRole("heading", { name: "Imported road-trip" })).toBeVisible();
  await expect(page.getByRole("row", { name: /Road repeater/ })).toContainText(
    "147.300000 MHz",
  );
  await expect(page.getByLabel("Notes")).toHaveValue(
    "Imported from road-trip.csv, CHIRP memory 1.",
  );

  await page.reload();
  await page.getByRole("button", { name: /Imported road-trip/ }).click();
  await expect(page.getByRole("row", { name: /Road repeater/ })).toBeVisible();

  await page.getByRole("link", { name: "Compile & export" }).click();
  await expect(
    page.getByRole("checkbox", { name: /Imported road-trip/ }),
  ).toBeVisible();
});
