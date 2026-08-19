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
  UserCatalogRecords,
} from "$lib/types";

let workspaceState: WorkspaceState | null = null;
let workspaceSaveQueue: Promise<void> = Promise.resolve();
let workspaceSaveRevision = 0;

async function loadUiTestApi() {
  if (import.meta.env.MODE !== "ui-test") return null;
  return import("../../tests/ui/support/api.mock");
}

export async function compileProfile(
  profile: string,
  target: string,
  outputPath: string | null,
  configuration: CompileConfiguration,
  catalog: WorkspaceCatalog,
): Promise<CompileResult> {
  const userCatalog = userCatalogFromWorkspace(catalog);
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) {
    return uiTestApi.compileProfile(
      profile,
      target,
      outputPath,
      configuration,
      userCatalog,
    );
  }

  return invoke<CompileResult>("compile_profile", {
    profile,
    target,
    outputPath,
    frequencySetIds: configuration.frequencySetIds,
    memoryStart: configuration.memoryStart,
    mapSetsToBanks: configuration.mapSetsToBanks,
    useFactorySets: configuration.useFactorySets,
    userFrequencyDefinitions: userCatalog.frequencyDefinitions,
    userFrequencySets: userCatalog.frequencySets,
  });
}

export async function loadCatalog(): Promise<WorkspaceCatalog> {
  const uiTestApi = await loadUiTestApi();
  const catalog = uiTestApi
    ? await uiTestApi.loadCatalog()
    : await invoke<WorkspaceCatalog>("load_catalog");
  workspaceState ??= await initializeWorkspace(catalog, uiTestApi);
  return mergeStoredUserCatalog(catalog, workspaceState.user_catalog);
}

async function initializeWorkspace(
  catalog: WorkspaceCatalog,
  uiTestApi: Awaited<ReturnType<typeof loadUiTestApi>>,
): Promise<WorkspaceState> {
  const legacyCatalog = readLegacyUserCatalog();
  const legacyRadios = readLegacyRadioInventory();
  const legacyPlans = readLegacyPlanPreferences();
  const initial: WorkspaceState = {
    schema_version: 1,
    user_catalog: legacyCatalog ?? userCatalogFromWorkspace(catalog),
    radios: legacyRadios ?? [{ ...defaultRadio }],
    profile_plan_ids: legacyPlans ?? Object.fromEntries(
      catalog.profiles.map((profile) => [profile.id, profile.frequency_plan_id]),
    ),
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
  await persistWorkspace({ ...requireWorkspace(), user_catalog: records });
}

export function loadProfilePlanPreference(profileId: string, fallback: string): string {
  return requireWorkspace().profile_plan_ids[profileId] ?? fallback;
}

export async function saveProfilePlanPreference(profileId: string, planId: string): Promise<void> {
  const current = requireWorkspace();
  await persistWorkspace({
    ...current,
    profile_plan_ids: { ...current.profile_plan_ids, [profileId]: planId },
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
  profile: string,
  target: string,
): Promise<string | null> {
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) return uiTestApi.chooseCsvOutputPath(profile, target);

  return save({
    title: "Export CHIRP CSV",
    defaultPath: `${profile}-${target}.csv`,
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
