import { readFile } from "node:fs/promises";

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));
const [baseConfig, releaseConfig, packageManifest] = await Promise.all([
  readJson("src-tauri/tauri.conf.json"),
  readJson("src-tauri/tauri.release.conf.json"),
  readJson("package.json"),
]);
const cargoManifest = await readFile("src-tauri/Cargo.toml", "utf8");

const manifestVersion = (source, label) => {
  const match = source.match(/^version\s*=\s*"([^"]+)"/m);
  if (!match) throw new Error(`Could not read the version from ${label}.`);
  return match[1];
};
const versions = {
  "package.json": packageManifest.version,
  "tauri.conf.json": baseConfig.version,
  "Cargo.toml": manifestVersion(cargoManifest, "Cargo.toml"),
};
if (new Set(Object.values(versions)).size !== 1) {
  throw new Error(`Release versions are not synchronized: ${JSON.stringify(versions)}`);
}

if (baseConfig.bundle?.createUpdaterArtifacts === true) {
  throw new Error("Normal local Tauri builds must not create updater artifacts.");
}
if (releaseConfig.bundle?.createUpdaterArtifacts !== true) {
  throw new Error("The release Tauri config must create updater artifacts.");
}

const expectedReleaseScripts = {
  "bundle:windows:release": "-Release",
  "bundle:linux:release": "--release",
  "bundle:macos:release": "--release",
};
for (const [name, marker] of Object.entries(expectedReleaseScripts)) {
  if (!packageManifest.scripts?.[name]?.includes(marker)) {
    throw new Error(`${name} must select explicit release mode.`);
  }
}

for (const path of [
  "scripts/build-portable.ps1",
  "scripts/build-linux.sh",
  "scripts/build-macos.sh",
]) {
  const script = await readFile(path, "utf8");
  if (
    script.includes("rigmanifest-updater.key") ||
    script.includes("rigmanifest-updater-password.txt")
  ) {
    throw new Error(`${path} must not discover local signing-key backups.`);
  }
}

const macosScript = await readFile("scripts/build-macos.sh", "utf8");
if (!macosScript.includes('APPLE_SIGNING_IDENTITY="-"')) {
  throw new Error("The macOS package must use an explicit ad-hoc signing identity.");
}
for (const credential of ["APPLE_CERTIFICATE", "APPLE_ID", "APPLE_PASSWORD"]) {
  if (macosScript.includes(credential)) {
    throw new Error(`The unsigned macOS package must not require ${credential}.`);
  }
}

console.log("Local and signed release packaging are separated.");
