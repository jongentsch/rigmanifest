import type { CompileResult } from "$lib/types";

import compileHome from "../fixtures/compile-home.json";

interface UiTestCall {
  method: "chooseCsvOutputPath" | "compileProfile";
  profile: string;
  target: string;
  outputPath?: string | null;
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
  outputPath: string | null = null,
): Promise<CompileResult> {
  record({ method: "compileProfile", profile, target, outputPath });

  if (profile !== "home" || target !== "yaesu-vx6r") {
    throw new Error(`Unsupported UI test fixture: ${profile}/${target}`);
  }

  const result = structuredClone(compileHome) as CompileResult;
  result.csv_path = outputPath;
  return result;
}

export async function chooseCsvOutputPath(
  profile: string,
  target: string,
): Promise<string> {
  record({ method: "chooseCsvOutputPath", profile, target });
  return `/exports/${profile}-${target}.csv`;
}
