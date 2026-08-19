import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";

import type { CompileResult } from "$lib/types";

async function loadUiTestApi() {
  if (import.meta.env.MODE !== "ui-test") {
    return null;
  }

  return import("../../tests/ui/support/api.mock");
}

export async function compileProfile(
  profile: string,
  target: string,
  outputPath: string | null = null,
): Promise<CompileResult> {
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) {
    return uiTestApi.compileProfile(profile, target, outputPath);
  }

  return invoke<CompileResult>("compile_profile", {
    profile,
    target,
    outputPath,
  });
}

export async function chooseCsvOutputPath(
  profile: string,
  target: string,
): Promise<string | null> {
  const uiTestApi = await loadUiTestApi();
  if (uiTestApi) {
    return uiTestApi.chooseCsvOutputPath(profile, target);
  }

  return save({
    title: "Export CHIRP CSV",
    defaultPath: `${profile}-${target}.csv`,
    filters: [{ name: "CHIRP CSV", extensions: ["csv"] }],
  });
}
