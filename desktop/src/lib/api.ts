import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";

import {
  clearLegacyUserCatalog,
  mergeStoredUserCatalog,
  readLegacyUserCatalog,
  userCatalogFromWorkspace,
} from "$lib/catalog";
import { clearLegacyPlanPreferences, readLegacyPlanPreferences } from "$lib/plan-preferences";
import {
  clearLegacyRadioInventory,
  defaultRadio,
  readLegacyRadioInventory,
} from "$lib/radios";
import type {
  CompileConfiguration,
  CompileResult,
  ChirpCatalogImportResult,
  WorkspaceCatalog,
  WorkspaceState,
  RadioInstance,
  ProfileRecord,
  UserCatalogRecords,
} from "$lib/types";

let workspaceState: WorkspaceState | null = null;
let builtinCatalog: WorkspaceCatalog | null = null;
let workspaceSaveQueue: Promise<void> = Promise.resolve();
let workspaceSaveRevision = 0;

async function loadUiTestApi() {
  if (import.meta.env.MODE !== "ui-test") return null;
  return import("../../tests/ui/support/api.mock");
}

export async function compileSelection(
  target: string,
  outputPath: string | null,
  profiles: ProfileRecord[],
  configuration: CompileConfiguration,
  catalog: WorkspaceCatalog,
): Promise<CompileResult> {
  const userCatalog = userCatalogFromWorkspace(catalog);
  const serializableProfiles = JSON.parse(JSON.stringify(profiles)) as ProfileRecord[];
  const serializableConfiguration = JSON.parse(
    JSON.stringify(configuration),
  ) as CompileConfiguration;
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) {
    return uiTestApi.compileSelection(
      target,
      outputPath,
      serializableProfiles,
      serializableConfiguration,
      userCatalog,
    );
  }

  return invoke<CompileResult>("compile_selection", {
    target,
    outputPath,
    profiles: serializableProfiles,
    additionalFrequencySetIds: serializableConfiguration.additionalFrequencySetIds,
    additionalFrequencyDefinitionIds: serializableConfiguration.additionalFrequencyDefinitionIds,
    advisoryPlanId: serializableConfiguration.advisoryPlanId,
    memoryStart: serializableConfiguration.memoryStart,
    mapSetsToBanks: serializableConfiguration.mapSetsToBanks,
    useFactorySets: serializableConfiguration.useFactorySets,
    userFrequencyDefinitions: userCatalog.frequencyDefinitions,
    userFrequencySets: userCatalog.frequencySets,
  });
}

export async function loadCatalog(): Promise<WorkspaceCatalog> {
  const uiTestApi = await loadUiTestApi();
  const catalog = uiTestApi
    ? await uiTestApi.loadCatalog()
    : await invoke<WorkspaceCatalog>("load_catalog");
  builtinCatalog = structuredClone(catalog);
  workspaceState ??= await initializeWorkspace(catalog, uiTestApi);
  return {
    ...mergeStoredUserCatalog(catalog, workspaceState.user_catalog),
    profiles: structuredClone(workspaceState.profiles),
  };
}

async function initializeWorkspace(
  catalog: WorkspaceCatalog,
  uiTestApi: Awaited<ReturnType<typeof loadUiTestApi>>,
): Promise<WorkspaceState> {
  const legacyCatalog = readLegacyUserCatalog();
  const legacyRadios = readLegacyRadioInventory();
  const legacyPlans = readLegacyPlanPreferences();
  const profiles = catalog.profiles.map((profile) => ({
    ...profile,
    frequency_plan_id: legacyPlans?.[profile.id] ?? profile.frequency_plan_id,
  }));
  const initial: WorkspaceState = {
    schema_version: 2,
    user_catalog: legacyCatalog ?? userCatalogFromWorkspace(catalog),
    radios: legacyRadios ?? [{ ...defaultRadio }],
    profiles,
    default_frequency_plan_id: "arrl-us-national",
  };
  const loaded = uiTestApi
    ? await uiTestApi.loadWorkspace(initial)
    : await invoke<WorkspaceState>("load_workspace", { legacyState: initial });
  if (loaded.migrated_legacy) {
    clearLegacyUserCatalog();
    clearLegacyRadioInventory();
    clearLegacyPlanPreferences();
  }
  return loaded;
}

function requireWorkspace(): WorkspaceState {
  if (!workspaceState) throw new Error("Workspace has not been loaded");
  return workspaceState;
}

async function persistWorkspace(next: WorkspaceState): Promise<void> {
  const serializable = JSON.parse(JSON.stringify(next)) as WorkspaceState;
  const revision = ++workspaceSaveRevision;
  workspaceState = serializable;
  const saveOperation = workspaceSaveQueue.catch(() => undefined).then(async () => {
    const uiTestApi = await loadUiTestApi();
    const saved = uiTestApi
      ? await uiTestApi.saveWorkspace(serializable)
      : await invoke<WorkspaceState>("save_workspace", { state: serializable });
    if (revision === workspaceSaveRevision) workspaceState = saved;
  });
  workspaceSaveQueue = saveOperation;
  await saveOperation;
}

export function loadRadioInventory(): RadioInstance[] {
  return structuredClone(requireWorkspace().radios);
}

export async function saveRadioInventory(radios: RadioInstance[]): Promise<void> {
  await persistWorkspace({ ...requireWorkspace(), radios });
}

export async function saveWorkspaceUserCatalog(records: UserCatalogRecords): Promise<void> {
  const workspace = requireWorkspace();
  const knownSetIds = new Set([
    ...(builtinCatalog?.frequency_sets ?? [])
      .filter((item) => item.read_only)
      .map((item) => item.id),
    ...records.frequencySets.map((item) => item.id),
  ]);
  const knownDefinitionIds = new Set([
    ...(builtinCatalog?.frequency_definitions ?? [])
      .filter((item) => item.read_only)
      .map((item) => item.id),
    ...records.frequencyDefinitions.map((item) => item.id),
  ]);
  const profiles = workspace.profiles.map((profile) => ({
    ...profile,
    frequency_set_ids: profile.frequency_set_ids.filter((id) => knownSetIds.has(id)),
    frequency_definition_ids: profile.frequency_definition_ids.filter((id) =>
      knownDefinitionIds.has(id)
    ),
  }));
  await persistWorkspace({ ...workspace, user_catalog: records, profiles });
}

export function loadProfiles(): ProfileRecord[] {
  return structuredClone(requireWorkspace().profiles);
}

export async function saveProfiles(profiles: ProfileRecord[]): Promise<void> {
  await persistWorkspace({ ...requireWorkspace(), profiles });
}

export function loadDefaultFrequencyPlan(): string | null {
  return requireWorkspace().default_frequency_plan_id;
}

export async function saveDefaultFrequencyPlan(planId: string | null): Promise<void> {
  await persistWorkspace({
    ...requireWorkspace(),
    default_frequency_plan_id: planId,
  });
}

export async function backupWorkspace(destination: string): Promise<string> {
  await workspaceSaveQueue;
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) return uiTestApi.backupWorkspace(destination);
  const result = await invoke<{ path: string }>("backup_workspace", { destination });
  return result.path;
}

export async function chooseWorkspaceBackupPath(): Promise<string | null> {
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) return uiTestApi.chooseWorkspaceBackupPath();
  return save({
    title: "Back up RigManifest workspace",
    defaultPath: "rigmanifest-backup.sqlite3",
    filters: [{ name: "SQLite database", extensions: ["sqlite3"] }],
  });
}

export async function chooseCsvOutputPath(
  selection: string,
  target: string,
): Promise<string | null> {
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) return uiTestApi.chooseCsvOutputPath(selection, target);

  return save({
    title: "Export CHIRP CSV",
    defaultPath: `${selection}-${target}.csv`,
    filters: [{ name: "CHIRP CSV", extensions: ["csv"] }],
  });
}

export async function chooseChirpImportPath(): Promise<string | null> {
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) return uiTestApi.chooseChirpImportPath();

  const selected = await open({
    title: "Import CHIRP CSV",
    multiple: false,
    directory: false,
    filters: [{ name: "CHIRP CSV", extensions: ["csv"] }],
  });
  return typeof selected === "string" ? selected : null;
}

export async function importChirpCsv(
  sourcePath: string,
): Promise<ChirpCatalogImportResult> {
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) return uiTestApi.importChirpCsv(sourcePath);
  return invoke<ChirpCatalogImportResult>("import_chirp_csv", { sourcePath });
}
