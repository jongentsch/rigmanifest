import type {
  FrequencyDefinitionRecord,
  FrequencySetRecord,
  SignalingSpec,
  UserCatalogRecords,
  WorkspaceCatalog,
} from "$lib/types";

const storageKey = "rigmanifest.user-catalog.v2";
const legacyStorageKey = "rigmanifest.user-catalog.v1";

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
  if (raw) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isUserCatalogRecords(parsed)) return parsed;
    } catch {
      // Fall through to the legacy migration.
    }
  }

  const legacyRaw = localStorage.getItem(legacyStorageKey);
  if (!legacyRaw) return null;
  try {
    const migrated = migrateLegacyCatalog(JSON.parse(legacyRaw));
    if (migrated) saveUserCatalog(migrated);
    return migrated;
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
    isSignaling(value.transmit_access) &&
    isSignaling(value.receive_squelch) &&
    Array.isArray(value.tags) &&
    value.tags.every((item) => typeof item === "string") &&
    typeof value.priority === "string" &&
    typeof value.notes === "string"
  );
}

function isSignaling(value: unknown): value is SignalingSpec {
  if (!isRecord(value)) return false;
  return (
    (value.kind === "none" || value.kind === "ctcss" || value.kind === "dcs") &&
    (value.ctcss_hz === null || typeof value.ctcss_hz === "number") &&
    (value.dcs_code === null || typeof value.dcs_code === "number") &&
    (value.dcs_polarity === "N" || value.dcs_polarity === "R")
  );
}

function migrateLegacyCatalog(value: unknown): UserCatalogRecords | null {
  if (!isRecord(value) || !Array.isArray(value.frequencyDefinitions)) return null;
  const frequencyDefinitions = value.frequencyDefinitions.map((definition) => {
    if (!isRecord(definition) || !isRecord(definition.tone)) return definition;
    const [transmit_access, receive_squelch] = migrateLegacyTone(definition.tone);
    const { tone: _tone, ...rest } = definition;
    return { ...rest, transmit_access, receive_squelch };
  });
  const candidate = { ...value, frequencyDefinitions };
  return isUserCatalogRecords(candidate) ? candidate : null;
}

function migrateLegacyTone(tone: Record<string, unknown>): [SignalingSpec, SignalingSpec] {
  const none = (): SignalingSpec => ({
    kind: "none",
    ctcss_hz: null,
    dcs_code: null,
    dcs_polarity: "N",
  });
  if (tone.mode === "tone") {
    return [{ kind: "ctcss", ctcss_hz: Number(tone.encode_hz), dcs_code: null, dcs_polarity: "N" }, none()];
  }
  if (tone.mode === "tsql") {
    return [
      { kind: "ctcss", ctcss_hz: Number(tone.encode_hz), dcs_code: null, dcs_polarity: "N" },
      { kind: "ctcss", ctcss_hz: Number(tone.decode_hz ?? tone.encode_hz), dcs_code: null, dcs_polarity: "N" },
    ];
  }
  if (tone.mode === "dtcs") {
    const polarity = typeof tone.dtcs_polarity === "string" ? tone.dtcs_polarity : "NN";
    return [
      { kind: "dcs", ctcss_hz: null, dcs_code: Number(tone.dtcs_code), dcs_polarity: polarity[0] === "R" ? "R" : "N" },
      { kind: "dcs", ctcss_hz: null, dcs_code: Number(tone.dtcs_code), dcs_polarity: polarity[1] === "R" ? "R" : "N" },
    ];
  }
  return [none(), none()];
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
