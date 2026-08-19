import type {
  FrequencyDefinitionRecord,
  FrequencySetRecord,
  UserCatalogRecords,
  WorkspaceCatalog,
} from "$lib/types";

const storageKey = "rigmanifest.user-catalog.v1";

export function userCatalogFromWorkspace(
  catalog: WorkspaceCatalog,
): UserCatalogRecords {
  return {
    frequencyDefinitions: catalog.frequency_definitions.filter(
      (item) => item.origin === "user" && !item.read_only,
    ),
    frequencySets: catalog.frequency_sets.filter(
      (item) => item.origin === "user" && !item.read_only,
    ),
  };
}

export function mergeStoredUserCatalog(
  base: WorkspaceCatalog,
): WorkspaceCatalog {
  const stored = readStoredUserCatalog();
  const userCatalog = stored ?? userCatalogFromWorkspace(base);
  if (!stored) saveUserCatalog(userCatalog);

  return {
    ...base,
    frequency_definitions: [
      ...userCatalog.frequencyDefinitions,
      ...base.frequency_definitions.filter((item) => item.origin === "preset"),
    ],
    frequency_sets: [
      ...userCatalog.frequencySets,
      ...base.frequency_sets.filter((item) => item.origin === "preset"),
    ],
  };
}

export function saveWorkspaceUserCatalog(catalog: WorkspaceCatalog): void {
  saveUserCatalog(userCatalogFromWorkspace(catalog));
}

function readStoredUserCatalog(): UserCatalogRecords | null {
  const raw = localStorage.getItem(storageKey);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return isUserCatalogRecords(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function saveUserCatalog(catalog: UserCatalogRecords): void {
  localStorage.setItem(storageKey, JSON.stringify(catalog));
}

function isUserCatalogRecords(value: unknown): value is UserCatalogRecords {
  if (!isRecord(value)) return false;
  return (
    Array.isArray(value.frequencyDefinitions) &&
    value.frequencyDefinitions.every(isUserDefinition) &&
    Array.isArray(value.frequencySets) &&
    value.frequencySets.every(isUserSet)
  );
}

function isUserDefinition(value: unknown): value is FrequencyDefinitionRecord {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    value.origin === "user" &&
    value.read_only === false &&
    typeof value.receive_frequency_hz === "number" &&
    typeof value.transmit_behavior === "string" &&
    typeof value.mode === "string" &&
    isRecord(value.tone) &&
    Array.isArray(value.tags) &&
    value.tags.every((item) => typeof item === "string") &&
    typeof value.priority === "string" &&
    typeof value.notes === "string"
  );
}

function isUserSet(value: unknown): value is FrequencySetRecord {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    value.origin === "user" &&
    value.read_only === false &&
    typeof value.description === "string" &&
    Array.isArray(value.members) &&
    value.members.every(
      (member) =>
        isRecord(member) &&
        typeof member.frequency_definition_id === "string" &&
        typeof member.position === "number" &&
        (member.channel_designator === null ||
          typeof member.channel_designator === "string"),
    )
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
