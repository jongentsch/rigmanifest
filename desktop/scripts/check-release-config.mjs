import { readFile } from "node:fs/promises";

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));
const [baseConfig, releaseConfig, packageManifest] = await Promise.all([
  readJson("src-tauri/tauri.conf.json"),
  readJson("src-tauri/tauri.release.conf.json"),
  readJson("package.json"),
]);

if (baseConfig.bundle?.createUpdaterArtifacts === true) {
  throw new Error("Normal local Tauri builds must not create updater artifacts.");
}
if (releaseConfig.bundle?.createUpdaterArtifacts !== true) {
  throw new Error("The release Tauri config must create updater artifacts.");
}

const expectedReleaseScripts = {
  "bundle:windows:release": "-Release",
  "bundle:linux:release": "--release",
};
for (const [name, marker] of Object.entries(expectedReleaseScripts)) {
  if (!packageManifest.scripts?.[name]?.includes(marker)) {
    throw new Error(`${name} must select explicit release mode.`);
  }
}

for (const path of ["scripts/build-portable.ps1", "scripts/build-linux.sh"]) {
  const script = await readFile(path, "utf8");
  if (
    script.includes("rigmanifest-updater.key") ||
    script.includes("rigmanifest-updater-password.txt")
  ) {
    throw new Error(`${path} must not discover local signing-key backups.`);
  }
}

console.log("Local and signed release packaging are separated.");
