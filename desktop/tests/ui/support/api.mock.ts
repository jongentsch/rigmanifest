import type {
  CompileConfiguration,
  CompileResult,
  ChirpCatalogImportResult,
  ChirpImageImportResult,
  RadioImageVersion,
  UserCatalogRecords,
  WorkspaceCatalog,
  WorkspaceState,
  ProfileRecord,
} from "$lib/types";

import catalogFixture from "../fixtures/catalog.json";
import compileHome from "../fixtures/compile-home.json";

interface UiTestCall {
  method: "backupWorkspace" | "chooseChirpImportPath" | "chooseChirpImagePath" | "chooseCsvOutputPath" | "chooseImageOutputPath" | "compileSelection" | "importChirpCsv" | "importChirpImage";
  profile: string;
  target: string;
  outputPath?: string | null;
  configuration?: CompileConfiguration;
  profiles?: ProfileRecord[];
  userCatalog?: UserCatalogRecords;
}

const workspaceKey = "rigmanifest.ui-test.sqlite-workspace.v1";
const radioImagesKey = "rigmanifest.ui-test.radio-images.v1";

function sourceVersion(radioId: string, filename = "Yaesu_VX-6.img"): RadioImageVersion {
  return {
    id: `source-${radioId}`,
    radio_id: radioId,
    kind: "source",
    path: `/workspace/radios/${radioId}/source.img`,
    filename,
    driver_reference: "Yaesu_VX-6",
    byte_size: 32_507,
    sha256: "a".repeat(64),
    created_at: "2026-08-19T12:00:00.000Z",
  };
}

function readImageVersions(radioId: string): RadioImageVersion[] {
  const stored = JSON.parse(localStorage.getItem(radioImagesKey) ?? "{}") as Record<string, RadioImageVersion[]>;
  return structuredClone(stored[radioId] ?? [sourceVersion(radioId)]);
}

function writeImageVersions(radioId: string, versions: RadioImageVersion[]): void {
  const stored = JSON.parse(localStorage.getItem(radioImagesKey) ?? "{}") as Record<string, RadioImageVersion[]>;
  stored[radioId] = structuredClone(versions);
  localStorage.setItem(radioImagesKey, JSON.stringify(stored));
}

export async function loadWorkspace(initial: WorkspaceState): Promise<WorkspaceState> {
  const fixtureRadio = {
    id: "default-vx6r",
    name: "My VX-6R",
    radioModelId: "chirp:Yaesu_VX-6",
    driverReference: "Yaesu_VX-6",
    manufacturer: "Yaesu",
    model: "VX-6",
    imageFilename: "Yaesu_VX-6.img",
    memoryCapacity: 999,
    maxLabelLength: 6,
    bankCount: 24,
    settingCount: 124,
    memoryStart: 1,
    mapSetsToBanks: true,
    notes: "",
  };
  const base = initial.radios.length ? initial : { ...initial, radios: [fixtureRadio] };
  const raw = localStorage.getItem(workspaceKey);
  if (raw) {
    const stored = JSON.parse(raw) as Partial<WorkspaceState>;
    const migrated: WorkspaceState = {
      ...structuredClone(base),
      ...stored,
      schema_version: 3,
      profiles: Array.isArray(stored.profiles)
        ? stored.profiles
        : structuredClone(base.profiles),
      default_frequency_plan_id:
        stored.default_frequency_plan_id ?? base.default_frequency_plan_id,
      migrated_legacy: stored.migrated_legacy ?? false,
    };
    localStorage.setItem(workspaceKey, JSON.stringify(migrated));
    return migrated;
  }
  const migrated = { ...structuredClone(base), migrated_legacy: true };
  localStorage.setItem(workspaceKey, JSON.stringify(migrated));
  return migrated;
}

export async function saveWorkspace(state: WorkspaceState): Promise<WorkspaceState> {
  const saved = { ...structuredClone(state), migrated_legacy: false };
  localStorage.setItem(workspaceKey, JSON.stringify(saved));
  return saved;
}

export async function chooseWorkspaceBackupPath(): Promise<string> {
  return "/backups/rigmanifest-backup.sqlite3";
}

export async function backupWorkspace(destination: string): Promise<string> {
  record({ method: "backupWorkspace", profile: destination, target: "" });
  return destination;
}

declare global {
  interface Window {
    __RIGMANIFEST_UI_TEST_CALLS__?: UiTestCall[];
  }
}

function record(call: UiTestCall): void {
  window.__RIGMANIFEST_UI_TEST_CALLS__ ??= [];
  window.__RIGMANIFEST_UI_TEST_CALLS__.push(call);
}

export async function compileSelection(
  target: string,
  outputPath: string | null,
  profiles: ProfileRecord[],
  configuration: CompileConfiguration,
  userCatalog: UserCatalogRecords,
): Promise<CompileResult> {
  record({
    method: "compileSelection",
    profile: profiles.map((profile) => profile.id).join(","),
    target,
    outputPath,
    configuration,
    profiles,
    userCatalog,
  });

  if (target !== "default-vx6r" && target !== "yaesu-vx6r") {
    throw new Error(`Unsupported UI test fixture: ${target}`);
  }

  const result = structuredClone(compileHome) as unknown as CompileResult;
  result.csv_path = outputPath;
  result.image_path = outputPath;
  if (outputPath) {
    const version: RadioImageVersion = {
      id: `compiled-${Date.now()}`,
      radio_id: target,
      kind: "compiled",
      path: `/workspace/radios/${target}/compiled.img`,
      filename: outputPath.split("/").at(-1) ?? "compiled.img",
      driver_reference: "Yaesu_VX-6",
      byte_size: 32_507,
      sha256: "b".repeat(64),
      created_at: "2026-08-19T13:00:00.000Z",
    };
    writeImageVersions(target, [version, ...readImageVersions(target)]);
    result.managed_image_path = version.path;
    result.image_version = version;
  }
  result.profiles = structuredClone(profiles);
  result.profile = structuredClone(profiles[0] ?? result.profile);
  result.selection = {
    additional_frequency_set_ids: [...configuration.additionalFrequencySetIds],
    additional_frequency_definition_ids: [
      ...configuration.additionalFrequencyDefinitionIds,
    ],
    advisory_plan_id: configuration.advisoryPlanId,
  };
  const selectedSetIds = new Set([
    ...profiles.flatMap((profile) => profile.frequency_set_ids),
    ...configuration.additionalFrequencySetIds,
  ]);

  if (!selectedSetIds.has("home-essentials")) {
    result.memories = [];
    result.summary.programmed = 0;
    result.capacity.used = 0;
  } else {
    result.memories = result.memories.map((memory, index) => ({
      ...memory,
      memory_number: configuration.memoryStart + index,
      source_profile_ids: profiles
        .filter((profile) =>
          profile.frequency_definition_ids.includes(memory.source_frequency_definition_id) ||
          profile.frequency_set_ids.some((setId) =>
            memory.source_frequency_set_ids.includes(setId)
          )
        )
        .map((profile) => profile.id),
      selected_directly:
        configuration.additionalFrequencyDefinitionIds.includes(
          memory.source_frequency_definition_id,
        ) ||
        memory.source_frequency_set_ids.some((setId) =>
          configuration.additionalFrequencySetIds.includes(setId)
        ),
      bank_assignments: configuration.mapSetsToBanks
        ? memory.source_frequency_set_ids
        : [],
    }));
  }

  const selectedSetOrder = [...new Set([
    ...profiles.flatMap((profile) => profile.frequency_set_ids),
    ...configuration.additionalFrequencySetIds,
  ])];
  const activeSetIds = selectedSetOrder.filter((setId) =>
    result.memories.some((memory) => memory.bank_assignments.includes(setId))
  );
  const setNames = new Map([
    ...catalogFixture.frequency_sets,
    ...userCatalog.frequencySets,
  ].map((frequencySet) => [frequencySet.id, frequencySet.name]));
  result.banks = configuration.mapSetsToBanks
    ? activeSetIds.map((setId, index) => ({
        bank_number: index + 1,
        frequency_set_id: setId,
        name: setNames.get(setId) ?? setId,
        memory_numbers: result.memories
          .filter((memory) => memory.bank_assignments.includes(setId))
          .map((memory) => memory.memory_number),
      }))
    : [];

  if (
    !selectedSetIds.has("us-noaa-weather") ||
    !configuration.useFactorySets
  ) {
    result.factory_sets = [];
    result.diagnostics = result.diagnostics.filter(
      (diagnostic) => diagnostic.code !== "FACTORY_SET_AVAILABLE",
    );
    result.summary.factory_sets = 0;
    result.summary.factory_provided = 0;
  }
  result.summary.included = result.summary.programmed + result.summary.factory_provided;
  return result;
}

export async function loadCatalog(): Promise<WorkspaceCatalog> {
  return structuredClone(catalogFixture) as unknown as WorkspaceCatalog;
}

export async function chooseCsvOutputPath(
  selection: string,
  target: string,
): Promise<string> {
  record({ method: "chooseCsvOutputPath", profile: selection, target });
  return `/exports/${selection}-${target}.csv`;
}

export async function chooseImageOutputPath(
  selection: string,
  target: string,
): Promise<string> {
  record({ method: "chooseImageOutputPath", profile: selection, target });
  return `/exports/${selection}-${target}.img`;
}

export async function chooseChirpImagePath(): Promise<string> {
  record({ method: "chooseChirpImagePath", profile: "", target: "" });
  return "/imports/Yaesu_VX-6.img";
}

export async function importChirpImage(
  radioId: string,
  sourcePath: string,
): Promise<ChirpImageImportResult> {
  record({ method: "importChirpImage", profile: sourcePath, target: radioId });
  const definitionId = `user-radio-${radioId}-memory-1`;
  const setId = `user-radio-${radioId}-bank-1`;
  const imageVersion = sourceVersion(radioId);
  writeImageVersions(radioId, [imageVersion]);
  return {
    source_path: sourcePath,
    source_filename: "Yaesu_VX-6.img",
    driver_reference: "Yaesu_VX-6",
    manufacturer: "Yaesu",
    model: "VX-6",
    definition_count: 1,
    bank_count: 24,
    setting_count: 124,
    memory_start: 1,
    memory_capacity: 999,
    max_label_length: 6,
    frequency_definitions: [{
      id: definitionId,
      name: "Calling",
      origin: "user",
      read_only: false,
      receive_frequency_hz: 146_520_000,
      transmit_behavior: "same",
      transmit_frequency_hz: null,
      offset_hz: null,
      mode: "FM",
      transmit_access: { kind: "none", ctcss_hz: null, dcs_code: null, dcs_polarity: "N" },
      receive_squelch: { kind: "none", ctcss_hz: null, dcs_code: null, dcs_polarity: "N" },
      tags: ["chirp-import"],
      priority: "normal",
      notes: "Imported from Yaesu_VX-6.img, CHIRP memory 1.",
      power_dbm: 36.99,
      power_label: "Hi",
      scan_skip: "",
      tuning_step_hz: 5000,
    }],
    frequency_sets: [{
      id: setId,
      name: "BANK 1",
      origin: "user",
      read_only: false,
      description: "Imported bank 1.",
      members: [{ frequency_definition_id: definitionId, position: 0, channel_designator: null }],
    }],
    profile: {
      id: `radio-${radioId}-image`,
      name: "Yaesu VX-6 image",
      description: "Imported image banks.",
      frequency_set_ids: [setId],
      frequency_definition_ids: [],
      frequency_plan_id: null,
    },
    image_version: imageVersion,
  };
}

export async function listRadioImages(radioId: string): Promise<RadioImageVersion[]> {
  return readImageVersions(radioId);
}

export async function chooseChirpImportPath(): Promise<string> {
  record({ method: "chooseChirpImportPath", profile: "", target: "" });
  return "/imports/road-trip.csv";
}

export async function importChirpCsv(
  sourcePath: string,
): Promise<ChirpCatalogImportResult> {
  record({ method: "importChirpCsv", profile: sourcePath, target: "" });
  const definitionId = "user-import-road-trip-test-1";
  return {
    source_path: sourcePath,
    definition_count: 1,
    frequency_definitions: [
      {
        id: definitionId,
        name: "Road repeater",
        origin: "user",
        read_only: false,
        receive_frequency_hz: 147_300_000,
        transmit_behavior: "offset",
        transmit_frequency_hz: null,
        offset_hz: 600_000,
        mode: "FM",
        transmit_access: {
          kind: "ctcss",
          ctcss_hz: 100,
          dcs_code: null,
          dcs_polarity: "N",
        },
        receive_squelch: {
          kind: "none",
          ctcss_hz: null,
          dcs_code: null,
          dcs_polarity: "N",
        },
        tags: ["chirp-import"],
        priority: "normal",
        notes: "Imported from road-trip.csv, CHIRP memory 1.",
      },
    ],
    frequency_set: {
      id: "user-set-import-road-trip-test",
      name: "Imported road-trip",
      origin: "user",
      read_only: false,
      description: "Imported from CHIRP CSV road-trip.csv.",
      members: [
        {
          frequency_definition_id: definitionId,
          position: 0,
          channel_designator: null,
        },
      ],
    },
  };
}
