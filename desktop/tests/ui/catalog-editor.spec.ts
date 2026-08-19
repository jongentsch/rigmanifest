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
  await expect(page.getByLabel("Transmit CTCSS Hz").locator("option")).toHaveCount(50);
  await page.getByLabel("Transmit CTCSS Hz").selectOption("123");
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
  await expect(
    page.getByRole("heading", { name: "VX-6R (USA) memory plan" }),
  ).toBeVisible();

  const calls = await page.evaluate(() =>
    (
      window as typeof window & {
        __RIGMANIFEST_UI_TEST_CALLS__?: Array<Record<string, unknown>>;
      }
    ).__RIGMANIFEST_UI_TEST_CALLS__,
  );
  const compileCall = calls?.filter((item) => item.method === "compileSelection").at(-1);
  expect(compileCall).toMatchObject({
    configuration: {
      additionalFrequencySetIds: expect.arrayContaining([
        expect.stringMatching(/^user-set-/),
      ]),
      additionalFrequencyDefinitionIds: [],
      advisoryPlanId: "arrl-us-national",
    },
    profiles: [expect.objectContaining({ id: "home" })],
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
    JSON.parse(localStorage.getItem("rigmanifest.ui-test.sqlite-workspace.v1") ?? "null")
      .user_catalog,
  );
  expect(migrated.frequencyDefinitions[0]).not.toHaveProperty("tone");
  expect(await page.evaluate(() => localStorage.getItem("rigmanifest.user-catalog.v1"))).toBeNull();
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

test("shows preset provenance without making the set editable", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("button", { name: /US NOAA Weather Broadcasts/ }).click();

  await expect(page.getByText("United States / North America · reviewed 2026-08-19")).toBeVisible();
  await expect(page.getByRole("link", { name: "NOAA Weather Radio" })).toHaveAttribute(
    "href",
    "https://www.weather.gov/nwr/station_listing",
  );
  await expect(page.getByText("Preset definitions cannot be edited.")).toBeVisible();
});

test("stores the library advisory context independently of profiles", async ({ page }) => {
  await page.goto("/library");

  const plan = page.getByLabel("Advisory context for definitions");
  await plan.selectOption("kansas-repeater-council");
  const receive = page.getByLabel("Receive MHz");
  await receive.fill("444.500000");
  await receive.press("Tab");

  const suggestion = page.getByLabel("Frequency plan suggestion");
  await expect(suggestion).toContainText("Kansas 70 cm repeater outputs");
  await expect(suggestion).toContainText("Suggested offset +5.000 MHz");

  await plan.selectOption("southern-nevada-repeater-council");
  await receive.fill("447.500000");
  await receive.press("Tab");
  await expect(suggestion).toContainText("Southern Nevada 70 cm repeater outputs");
  await expect(suggestion).toContainText("Suggested offset -5.000 MHz");

  await page.reload();
  await expect(plan).toHaveValue("southern-nevada-repeater-council");
});

test("selects a frequency definition by clicking anywhere in its row", async ({ page }) => {
  await page.goto("/library");

  const repeaterRow = page.getByRole("row", { name: /70cm Local Repeater/ });
  await repeaterRow.getByText("444.500000 MHz").click();

  await expect(
    page.getByRole("heading", { name: "70cm Local Repeater", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Receive MHz")).toHaveValue("444.5");
  await expect(page.getByLabel("Frequency catalog summary")).toHaveCount(0);
});

test("backs up the durable workspace through the native boundary", async ({ page }) => {
  await page.goto("/library");

  await page.getByRole("button", { name: "Back up data" }).click();

  await expect(page.getByRole("status")).toContainText(
    "/backups/rigmanifest-backup.sqlite3",
  );
  const calls = await page.evaluate(() =>
    (
      window as typeof window & {
        __RIGMANIFEST_UI_TEST_CALLS__?: Array<Record<string, unknown>>;
      }
    ).__RIGMANIFEST_UI_TEST_CALLS__,
  );
  expect(calls).toContainEqual({
    method: "backupWorkspace",
    profile: "/backups/rigmanifest-backup.sqlite3",
    target: "",
  });
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
