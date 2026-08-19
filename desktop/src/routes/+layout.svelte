<script lang="ts">
  import { page } from "$app/state";
  import { onMount } from "svelte";

  import {
    automaticCheckIsDue,
    automaticUpdateChecksEnabled,
    checkForUpdates,
    currentUpdateSnapshot,
    initializeUpdates,
    installAvailableUpdate,
    openLatestRelease,
    subscribeToUpdates,
    type UpdateSnapshot,
  } from "$lib/updates";

  import "../app.css";

  type ThemePreference = "dark" | "light" | "system";

  const themeStorageKey = "rigmanifest-theme";

  let { children } = $props();
  let themePreference = $state<ThemePreference>("dark");
  let systemTheme: MediaQueryList | null = null;
  let updateState = $state<UpdateSnapshot>(currentUpdateSnapshot());

  onMount(() => {
    const storedTheme = localStorage.getItem(themeStorageKey);
    if (isThemePreference(storedTheme)) themePreference = storedTheme;

    systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
    systemTheme.addEventListener("change", handleSystemThemeChange);
    applyTheme(themePreference);

    const unsubscribeUpdates = subscribeToUpdates((next) => updateState = next);
    void initializeUpdates()
      .then(() => {
        if (automaticUpdateChecksEnabled() && automaticCheckIsDue()) {
          void checkForUpdates(true);
        }
      })
      .catch(() => undefined);

    return () => {
      systemTheme?.removeEventListener("change", handleSystemThemeChange);
      unsubscribeUpdates();
    };
  });

  function isThemePreference(value: string | null): value is ThemePreference {
    return value === "dark" || value === "light" || value === "system";
  }

  function resolvedTheme(preference: ThemePreference): "dark" | "light" {
    if (preference !== "system") return preference;
    return systemTheme?.matches ? "dark" : "light";
  }

  function applyTheme(preference: ThemePreference): void {
    const theme = resolvedTheme(preference);
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.themePreference = preference;
    document.documentElement.style.colorScheme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#20262c" : "#f4f1e9");
  }

  function changeTheme(event: Event): void {
    const value = (event.currentTarget as HTMLSelectElement).value;
    if (!isThemePreference(value)) return;

    themePreference = value;
    localStorage.setItem(themeStorageKey, value);
    applyTheme(value);
  }

  function handleSystemThemeChange(): void {
    if (themePreference === "system") applyTheme("system");
  }

  function routeIs(path: string): boolean {
    return page.url.pathname === path || page.url.pathname.startsWith(`${path}/`);
  }
</script>

<div class="workbench-shell">
  <aside class="app-sidebar">
    <a class="sidebar-brand" href="/compile" aria-label="RigManifest home">
      <img class="brand-logo" src="/rigmanifest-logo.png" alt="" aria-hidden="true" />
      <span>
        <strong>RigManifest</strong>
        <small>Configuration compiler</small>
      </span>
    </a>

    <nav class="sidebar-nav" aria-label="Workspace sections">
      <a class:active={routeIs("/library")} href="/library">
        <span>Frequency library</span>
      </a>
      <a class:active={routeIs("/radios")} href="/radios">
        <span>My radios</span>
      </a>
      <a class:active={routeIs("/profiles")} href="/profiles">
        <span>Profiles</span>
      </a>
      <a class:active={routeIs("/compile")} href="/compile">
        <span>Compile & export</span>
      </a>
      <a class:active={routeIs("/settings")} href="/settings">
        <span>Settings</span>
      </a>
    </nav>

    <div class="sidebar-spacer"></div>

    <div class="sidebar-connection">
      <span class="connection-dot"></span>
      <div>
        <strong>Saved locally</strong>
        <span>Private SQLite data</span>
      </div>
    </div>

    <label class="theme-control">
      <span>Appearance</span>
      <select value={themePreference} onchange={changeTheme} aria-label="Color theme">
        <option value="dark">Dark</option>
        <option value="light">Light</option>
        <option value="system">System</option>
      </select>
    </label>
  </aside>

  {#if updateState.status === "available"}
    <aside class="update-toast" aria-live="polite" aria-label="RigManifest update available">
      <div>
        <span class="section-label">Update available</span>
        <strong>RigManifest {updateState.availableVersion}</strong>
        <small>{updateState.canInstall ? "A signed update is ready to install." : "A new package is available on GitHub."}</small>
      </div>
      <div class="update-toast-actions">
        {#if updateState.canInstall}
          <button class="button button--primary" onclick={() => void installAvailableUpdate().catch(() => undefined)}>Install & restart</button>
        {:else}
          <button class="button button--primary" onclick={() => void openLatestRelease().catch(() => undefined)}>View download</button>
        {/if}
        <a href="/settings">Details</a>
      </div>
    </aside>
  {/if}

  {@render children()}
</div>
