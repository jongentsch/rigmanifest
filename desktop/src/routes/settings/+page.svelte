<script lang="ts">
  import { onMount } from "svelte";

  import {
    applyTextScale,
    loadTextScale,
    saveTextScale,
    textScaleOptions,
    type TextScale,
  } from "$lib/appearance";

  import {
    automaticUpdateChecksEnabled,
    checkForUpdates,
    currentUpdateSnapshot,
    initializeUpdates,
    installAvailableUpdate,
    openLatestRelease,
    setAutomaticUpdateChecks,
    subscribeToUpdates,
    type DistributionChannel,
    type UpdateSnapshot,
  } from "$lib/updates";

  let updateState = $state<UpdateSnapshot>(currentUpdateSnapshot());
  let automaticChecks = $state(true);
  let textScale = $state<TextScale>("1");

  onMount(() => {
    textScale = loadTextScale();
    applyTextScale(textScale);
    automaticChecks = automaticUpdateChecksEnabled();
    const unsubscribe = subscribeToUpdates((next) => updateState = next);
    void initializeUpdates().catch(() => undefined);
    return unsubscribe;
  });

  function changeAutomaticChecks(event: Event): void {
    automaticChecks = (event.currentTarget as HTMLInputElement).checked;
    setAutomaticUpdateChecks(automaticChecks);
  }

  function changeTextScale(event: Event): void {
    textScale = (event.currentTarget as HTMLSelectElement).value as TextScale;
    saveTextScale(textScale);
  }

  function channelName(channel: DistributionChannel): string {
    const names: Record<DistributionChannel, string> = {
      development: "Development build",
      "windows-installed": "Windows installer",
      "windows-portable": "Windows portable",
      "linux-appimage": "Linux AppImage",
      "linux-deb": "Linux Debian package",
      "macos-installed": "macOS application",
      unsupported: "Unsupported platform",
    };
    return names[channel];
  }

  function statusMessage(state: UpdateSnapshot): string {
    if (state.status === "checking") return "Checking GitHub Releases…";
    if (state.status === "up-to-date") return "You have the latest published version.";
    if (state.status === "available") return `Version ${state.availableVersion} is available.`;
    if (state.status === "backing-up") return "Backing up the workspace before updating…";
    if (state.status === "downloading") {
      return state.progress === null ? "Downloading the signed update…" : `Downloading the signed update… ${state.progress}%`;
    }
    if (state.status === "installing") return "Installing the verified update…";
    if (state.status === "error") return state.error ?? "The update check failed.";
    return "Automatic checks use the latest signed GitHub Release.";
  }

  let busy = $derived(["checking", "backing-up", "downloading", "installing"].includes(updateState.status));
</script>

<svelte:head>
  <title>Settings · RigManifest</title>
</svelte:head>

<main class="workspace">
  <header class="workspace-header">
    <div>
      <p class="workspace-kicker">Application</p>
      <h1>Settings</h1>
      <p>Control appearance, update checks, and application maintenance.</p>
    </div>
  </header>

  <div class="settings-layout">
    <div class="settings-primary">
      <section class="workspace-panel settings-panel" aria-labelledby="appearance-heading">
        <div class="panel-heading">
          <div>
            <p class="section-label">Readability</p>
            <h2 id="appearance-heading">Appearance</h2>
          </div>
        </div>
        <div class="settings-content">
          <label class="settings-field">
            <span>Text scale</span>
            <select aria-label="Text scale" aria-describedby="text-scale-description" value={textScale} onchange={changeTextScale}>
              {#each textScaleOptions as option}<option value={option.value}>{option.label}</option>{/each}
            </select>
            <small id="text-scale-description">Scales all interface text while preserving the existing size hierarchy.</small>
          </label>
        </div>
      </section>

      <section class="workspace-panel settings-panel" aria-labelledby="updates-heading">
      <div class="panel-heading">
        <div>
          <p class="section-label">GitHub Releases</p>
          <h2 id="updates-heading">Application updates</h2>
        </div>
        <span class="schema-label">v{updateState.currentVersion}</span>
      </div>

      <div class="settings-content">
        <dl class="settings-facts">
          <div><dt>Installed version</dt><dd>{updateState.currentVersion}</dd></div>
          <div><dt>Distribution</dt><dd>{channelName(updateState.channel)}</dd></div>
          <div><dt>Update mode</dt><dd>{updateState.canInstall ? "Signed in-app installation" : "Notification and manual download"}</dd></div>
        </dl>

        <label class="settings-toggle">
          <input type="checkbox" checked={automaticChecks} onchange={changeAutomaticChecks} />
          <span>
            <strong>Check automatically</strong>
            <small>Check at startup at most once every 24 hours. Updates are never installed without approval.</small>
          </span>
        </label>

        <div class:banner--error={updateState.status === "error"} class:banner--success={updateState.status === "up-to-date"} class="banner settings-status" aria-live="polite">
          <span>{statusMessage(updateState)}</span>
        </div>

        {#if updateState.releaseNotes}
          <div class="release-notes">
            <span class="section-label">Release notes</span>
            <p>{updateState.releaseNotes}</p>
          </div>
        {/if}

        {#if updateState.backupPath}
          <p class="backup-note">Workspace backup: <code>{updateState.backupPath}</code></p>
        {/if}

        <div class="settings-actions">
          <button class="button button--secondary" disabled={busy} onclick={() => void checkForUpdates()}>Check for updates</button>
          {#if updateState.status === "available" && updateState.canInstall}
            <button class="button button--primary" disabled={busy} onclick={() => void installAvailableUpdate().catch(() => undefined)}>Back up, install & restart</button>
          {:else if updateState.status === "available"}
            <button class="button button--primary" disabled={busy} onclick={() => void openLatestRelease().catch(() => undefined)}>Open GitHub download</button>
          {/if}
        </div>
      </div>
      </section>
    </div>

    <aside class="workspace-panel settings-help" aria-label="Update information">
      <div class="panel-heading"><h2>How updates work</h2></div>
      <div>
        <p>Every update is cryptographically signed and verified before installation.</p>
        <p>Installed Windows and AppImage builds can update in place. Portable ZIP and Debian builds link to the matching GitHub Release.</p>
        <p>Before an in-app update, RigManifest writes a SQLite backup and copies the managed <code>radios</code> directory into the workspace’s <code>backups</code> directory.</p>
      </div>
    </aside>
  </div>
</main>
