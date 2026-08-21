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
  await expect(page.getByRole("heading", { name: "Power capability" })).toBeVisible();
  await expect(page.getByLabel("Detected power levels")).toContainText("maximum");
  await expect(page.getByLabel("Detected power levels")).toContainText("Hi · 5 W nominal");
  await expect(page.locator(".power-level-list > span > strong")).toHaveText([
    "maximum",
    "high",
    "low",
    "minimum",
  ]);

  const calls = await page.evaluate(() => window.__RIGMANIFEST_UI_TEST_CALLS__);
  expect(calls).toContainEqual(expect.objectContaining({
    method: "importChirpImage",
    profile: "/imports/Yaesu_VX-6.img",
  }));
});

test("explains and remembers the Radio Default fallback", async ({ page }) => {
  await page.addInitScript(() => {
    const workspaceKey = "rigmanifest.ui-test.sqlite-workspace.v1";
    if (localStorage.getItem(workspaceKey)) return;
    localStorage.setItem(workspaceKey, JSON.stringify({
      radios: [{
        id: "missing-power",
        name: "Legacy handheld",
        radioModelId: "chirp:Yaesu_VX-6",
        driverReference: "Yaesu_VX-6",
        manufacturer: "Yaesu",
        model: "VX-6",
        imageFilename: "legacy.img",
        memoryStart: 1,
        mapSetsToBanks: true,
        notes: "",
      }],
    }));
  });
  await page.goto("/radios");

  await expect(page.getByText("Power level information is missing")).toBeVisible();
  await expect(page.getByText(/Import a newer image to try again/)).toBeVisible();
  await page.getByRole("button", { name: "Use Radio Default" }).click();
  await expect(page.getByText("Radio Default accepted")).toBeVisible();

  await page.reload();
  await expect(page.getByText("Radio Default accepted")).toBeVisible();
});

test("persists the user-facing name without changing detected model facts", async ({ page }) => {
  await page.goto("/radios");
  await page.getByLabel("Radio name").fill("Trail handheld");
  await page.getByRole("button", { name: "Save radio" }).click();

  await page.reload();

  await expect(page.getByLabel("Radio name")).toHaveValue("Trail handheld");
  await expect(page.getByLabel("Detected model")).toHaveValue("Yaesu VX-6");
});
