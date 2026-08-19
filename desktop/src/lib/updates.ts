import { getVersion } from "@tauri-apps/api/app";
import { invoke } from "@tauri-apps/api/core";
import { relaunch } from "@tauri-apps/plugin-process";
import { open } from "@tauri-apps/plugin-shell";
import { check, type DownloadEvent, type Update } from "@tauri-apps/plugin-updater";

export type DistributionChannel =
  | "development"
  | "windows-installed"
  | "windows-portable"
  | "linux-appimage"
  | "linux-deb"
  | "unsupported";

export type UpdateStatus =
  | "idle"
  | "checking"
  | "available"
  | "up-to-date"
  | "backing-up"
  | "downloading"
  | "installing"
  | "error";

export interface UpdateSnapshot {
  status: UpdateStatus;
  channel: DistributionChannel;
  currentVersion: string;
  availableVersion: string | null;
  releaseNotes: string | null;
  canInstall: boolean;
  progress: number | null;
  backupPath: string | null;
  error: string | null;
}

export const RELEASES_URL = "https://github.com/jongentsch/rigmanifest/releases/latest";
export const AUTOMATIC_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000;

const automaticChecksKey = "rigmanifest-automatic-update-checks";
const lastCheckKey = "rigmanifest-last-update-check";
const listeners = new Set<(snapshot: UpdateSnapshot) => void>();
const uiTestMode = import.meta.env.MODE === "ui-test";

let initialized = false;
let pendingUpdate: Update | null = null;
let snapshot: UpdateSnapshot = {
  status: "idle",
  channel: "development",
  currentVersion: "0.1.0",
  availableVersion: null,
  releaseNotes: null,
  canInstall: false,
  progress: null,
  backupPath: null,
  error: null,
};

function publish(changes: Partial<UpdateSnapshot>): UpdateSnapshot {
  snapshot = { ...snapshot, ...changes };
  for (const listener of listeners) listener({ ...snapshot });
  return { ...snapshot };
}

function installSupported(channel: DistributionChannel): boolean {
  return channel === "windows-installed" || channel === "linux-appimage";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function subscribeToUpdates(
  listener: (snapshot: UpdateSnapshot) => void,
): () => void {
  listeners.add(listener);
  listener({ ...snapshot });
  return () => listeners.delete(listener);
}

export function currentUpdateSnapshot(): UpdateSnapshot {
  return { ...snapshot };
}

export async function initializeUpdates(): Promise<UpdateSnapshot> {
  if (initialized) return currentUpdateSnapshot();

  if (uiTestMode) {
    initialized = true;
    return publish({ channel: "development", currentVersion: "0.1.0" });
  }

  const [channel, currentVersion] = await Promise.all([
    invoke<DistributionChannel>("distribution_channel"),
    getVersion(),
  ]);
  initialized = true;
  return publish({
    channel,
    currentVersion,
    canInstall: installSupported(channel),
  });
}

export function automaticUpdateChecksEnabled(): boolean {
  return localStorage.getItem(automaticChecksKey) !== "false";
}

export function setAutomaticUpdateChecks(enabled: boolean): void {
  localStorage.setItem(automaticChecksKey, String(enabled));
}

export function automaticCheckIsDue(
  now = Date.now(),
  lastCheck = localStorage.getItem(lastCheckKey),
): boolean {
  if (!lastCheck) return true;
  const checkedAt = Number(lastCheck);
  return !Number.isFinite(checkedAt) || now - checkedAt >= AUTOMATIC_CHECK_INTERVAL_MS;
}

export async function checkForUpdates(automatic = false): Promise<UpdateSnapshot> {
  await initializeUpdates();
  if (snapshot.status === "checking") return currentUpdateSnapshot();

  publish({ status: "checking", error: null, progress: null, backupPath: null });
  try {
    if (uiTestMode) {
      localStorage.setItem(lastCheckKey, String(Date.now()));
      return publish({ status: "up-to-date" });
    }

    const update = await check({ timeout: 20_000 });
    localStorage.setItem(lastCheckKey, String(Date.now()));
    if (!update) {
      if (pendingUpdate) void pendingUpdate.close();
      pendingUpdate = null;
      return publish({
        status: "up-to-date",
        availableVersion: null,
        releaseNotes: null,
      });
    }

    if (pendingUpdate) void pendingUpdate.close();
    pendingUpdate = update;
    return publish({
      status: "available",
      availableVersion: update.version,
      releaseNotes: update.body ?? null,
      canInstall: installSupported(snapshot.channel),
    });
  } catch (error) {
    if (automatic) localStorage.setItem(lastCheckKey, String(Date.now()));
    return publish({ status: "error", error: errorMessage(error) });
  }
}

export async function installAvailableUpdate(): Promise<void> {
  if (!pendingUpdate || !snapshot.canInstall) {
    throw new Error("This RigManifest distribution requires a manual update.");
  }

  try {
    publish({ status: "backing-up", error: null, progress: null });
    const backup = await invoke<{ path: string }>("backup_before_update", {
      targetVersion: pendingUpdate.version,
    });
    publish({ status: "downloading", backupPath: backup.path, progress: 0 });

    let downloaded = 0;
    let contentLength: number | undefined;
    const onDownload = (event: DownloadEvent): void => {
      if (event.event === "Started") {
        contentLength = event.data.contentLength;
        publish({ progress: contentLength ? 0 : null });
      } else if (event.event === "Progress") {
        downloaded += event.data.chunkLength;
        publish({
          progress: contentLength
            ? Math.min(100, Math.round((downloaded / contentLength) * 100))
            : null,
        });
      } else {
        publish({ status: "installing", progress: 100 });
      }
    };

    await pendingUpdate.downloadAndInstall(onDownload, { timeout: 120_000 });
    await relaunch();
  } catch (error) {
    publish({ status: "error", error: errorMessage(error) });
    throw error;
  }
}

export async function openLatestRelease(): Promise<void> {
  if (uiTestMode) return;
  await open(RELEASES_URL);
}
