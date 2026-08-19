import type { FrequencyPlanRecord, ProfileRecord } from "$lib/types";

const storageKey = "rigmanifest.frequency-plan-preferences.v1";

export function loadPlanPreference(
  profile: ProfileRecord,
  preferences: Record<string, string>,
): string {
  return preferences[profile.id] ?? profile.frequency_plan_id;
}

export function readLegacyPlanPreferences(): Record<string, string> | null {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) ?? "{}") as Record<string, unknown>;
    const valid = Object.entries(stored).filter(
      (entry): entry is [string, string] => typeof entry[1] === "string",
    );
    return valid.length > 0 ? Object.fromEntries(valid) : null;
  } catch {
    return null;
  }
}

export function clearLegacyPlanPreferences(): void {
  localStorage.removeItem(storageKey);
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
