import type {
  CompileConfiguration,
  CompileResult,
  UserCatalogRecords,
  WorkspaceCatalog,
} from "$lib/types";

import catalogFixture from "../fixtures/catalog.json";
import compileHome from "../fixtures/compile-home.json";

interface UiTestCall {
  method: "chooseCsvOutputPath" | "compileProfile";
  profile: string;
  target: string;
  outputPath?: string | null;
  configuration?: CompileConfiguration;
  userCatalog?: UserCatalogRecords;
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
