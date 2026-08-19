import type { FrequencyPlanRecord, ProfileRecord } from "$lib/types";

const storageKey = "rigmanifest.frequency-plan-preferences.v1";

export function loadPlanPreference(profile: ProfileRecord): string {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) ?? "{}") as Record<string, unknown>;
    const selected = stored[profile.id];
    return typeof selected === "string" ? selected : profile.frequency_plan_id;
  } catch {
    return profile.frequency_plan_id;
  }
}

export function savePlanPreference(profileId: string, frequencyPlanId: string): void {
  let stored: Record<string, unknown> = {};
  try {
    stored = JSON.parse(localStorage.getItem(storageKey) ?? "{}") as Record<string, unknown>;
  } catch {
    // Replace malformed preference data with the new explicit selection.
  }
  stored[profileId] = frequencyPlanId;
  localStorage.setItem(storageKey, JSON.stringify(stored));
}

export function advicePlans(
  plans: FrequencyPlanRecord[],
  selectedPlanId: string,
): FrequencyPlanRecord[] {
  const selected = plans.find((plan) => plan.id === selectedPlanId);
  const national = plans.find((plan) => plan.id === "arrl-us-national");
  return [selected, national].filter(
    (plan, index, values): plan is FrequencyPlanRecord =>
      Boolean(plan) && values.indexOf(plan) === index,
  );
}
