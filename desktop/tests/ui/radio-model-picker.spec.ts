import { expect, test } from "@playwright/test";

test("searches radio models by manufacturer or model and persists the choice", async ({
  page,
}) => {
  await page.goto("/radios");
  await expect(page.getByRole("heading", { name: "My radios" })).toBeVisible();

  const search = page.getByLabel("Find manufacturer or model");
  await expect(search).toHaveValue("Yaesu VX-6R (USA)");

  await search.fill("retevis");
  await expect(page.getByRole("heading", { name: "Retevis", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Quansheng" })).toHaveCount(0);
  await page.getByRole("button", { name: /RT95/ }).click();

  await expect(search).toHaveValue("Retevis RT95");
  await expect(page.locator(".model-facts")).toContainText("200");
  await expect(page.locator(".model-facts")).toContainText("None");
  await page.getByRole("button", { name: "Save radio" }).click();
  await expect(page.getByRole("status")).toContainText("Radio saved");

  await page.reload();
  await expect(search).toHaveValue("Retevis RT95");

  await search.fill("uv-k5");
  await expect(page.getByRole("heading", { name: "Quansheng" })).toBeVisible();
  await expect(page.getByRole("button", { name: /UV-K5/ })).toBeVisible();
});


test("reports an empty model search without changing the selected target", async ({
  page,
}) => {
  await page.goto("/radios");
  const search = page.getByLabel("Find manufacturer or model");

  await search.fill("not-a-real-radio");

  await expect(page.getByText(/No radio models match/)).toBeVisible();
  await expect(page.locator(".model-facts")).toContainText("900");
});
