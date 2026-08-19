import type {
  CompileConfiguration,
  CompileResult,
  ChirpCatalogImportResult,
  UserCatalogRecords,
  WorkspaceCatalog,
  WorkspaceState,
} from "$lib/types";

import catalogFixture from "../fixtures/catalog.json";
import compileHome from "../fixtures/compile-home.json";

interface UiTestCall {
  method: "backupWorkspace" | "chooseChirpImportPath" | "chooseCsvOutputPath" | "compileProfile" | "importChirpCsv";
  profile: string;
  target: string;
  outputPath?: string | null;
  configuration?: CompileConfiguration;
  userCatalog?: UserCatalogRecords;
}

const workspaceKey = "rigmanifest.ui-test.sqlite-workspace.v1";

export async function loadWorkspace(initial: WorkspaceState): Promise<WorkspaceState> {
  const raw = localStorage.getItem(workspaceKey);
  if (raw) return JSON.parse(raw) as WorkspaceState;
  const migrated = { ...structuredClone(initial), migrated_legacy: true };
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

export async function compileProfile(
  profile: string,
  target: string,
  outputPath: string | null,
  configuration: CompileConfiguration,
  userCatalog: UserCatalogRecords,
): Promise<CompileResult> {
  record({
    method: "compileProfile",
    profile,
    target,
    outputPath,
    configuration,
    userCatalog,
  });

  if (profile !== "home" || target !== "yaesu-vx6r") {
    throw new Error(`Unsupported UI test fixture: ${profile}/${target}`);
  }

  const result = structuredClone(compileHome) as unknown as CompileResult;
  result.csv_path = outputPath;
  result.profile.frequency_set_ids = [...configuration.frequencySetIds];

  if (!configuration.frequencySetIds.includes("home-essentials")) {
    result.memories = [];
    result.summary.programmed = 0;
    result.capacity.used = 0;
  } else {
    result.memories = result.memories.map((memory, index) => ({
      ...memory,
      memory_number: configuration.memoryStart + index,
      bank_assignments: configuration.mapSetsToBanks
        ? memory.source_frequency_set_ids
        : [],
    }));
  }

  if (
    !configuration.frequencySetIds.includes("us-noaa-weather") ||
    !configuration.useFactorySets
  ) {
    result.factory_sets = [];
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
  profile: string,
  target: string,
): Promise<string> {
  record({ method: "chooseCsvOutputPath", profile, target });
  return `/exports/${profile}-${target}.csv`;
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
