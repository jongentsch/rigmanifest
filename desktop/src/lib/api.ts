import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";

import { mergeStoredUserCatalog, userCatalogFromWorkspace } from "$lib/catalog";
import type {
  CompileConfiguration,
  CompileResult,
  WorkspaceCatalog,
} from "$lib/types";

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
  return mergeStoredUserCatalog(catalog);
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
