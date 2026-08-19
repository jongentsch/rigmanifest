import { invoke } from "@tauri-apps/api/core";

import type { CompileResult } from "$lib/types";

export async function compileProfile(
  profile: string,
  target: string,
  outputPath: string | null = null,
): Promise<CompileResult> {
  return invoke<CompileResult>("compile_profile", {
    profile,
    target,
    outputPath,
  });
}
