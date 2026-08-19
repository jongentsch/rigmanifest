<script lang="ts">
  import { onMount } from "svelte";
  import { save } from "@tauri-apps/plugin-dialog";

  import { compileProfile } from "$lib/api";
  import type {
    ChannelRecord,
    CompileResult,
    CompiledMemory,
    Diagnostic,
  } from "$lib/types";

  type ThemePreference = "dark" | "light" | "system";

  const themeStorageKey = "rigmanifest-theme";

  let profileId = $state("home");
  let targetId = $state("yaesu-vx6r");
  let plan = $state<CompileResult | null>(null);
  let busy = $state(false);
  let exporting = $state(false);
  let failure = $state("");
  let exportedPath = $state("");
  let themePreference = $state<ThemePreference>("dark");
  let systemTheme: MediaQueryList | null = null;

  onMount(() => {
    const storedTheme = localStorage.getItem(themeStorageKey);
    if (isThemePreference(storedTheme)) themePreference = storedTheme;

    systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
    systemTheme.addEventListener("change", handleSystemThemeChange);
    applyTheme(themePreference);
    void runCompile();

    return () => systemTheme?.removeEventListener("change", handleSystemThemeChange);
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
      ?.setAttribute("content", theme === "dark" ? "#171a1e" : "#f4f1e9");
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

  function errorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    if (error instanceof Error) return error.message;
    return "The compiler could not be reached.";
  }

  async function runCompile(): Promise<void> {
    busy = true;
    failure = "";
    exportedPath = "";
    try {
      plan = await compileProfile(profileId, targetId);
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      busy = false;
    }
  }

  async function exportCsv(): Promise<void> {
    failure = "";
    const outputPath = await save({
      title: "Export CHIRP CSV",
      defaultPath: `${profileId}-${targetId}.csv`,
      filters: [{ name: "CHIRP CSV", extensions: ["csv"] }],
    });
    if (!outputPath) return;

    exporting = true;
    try {
      plan = await compileProfile(profileId, targetId, outputPath);
      exportedPath = outputPath;
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      exporting = false;
    }
  }

  function mhz(frequencyHz: number): string {
    return `${(frequencyHz / 1_000_000).toFixed(6)} MHz`;
  }

  function offsetSummary(offsetHz: number): string {
    const sign = offsetHz > 0 ? "+" : "-";
    return `${sign}${(Math.abs(offsetHz) / 1_000_000).toFixed(3)} MHz`;
  }

  function txSummary(memory: CompiledMemory): string {
    if (memory.transmit_behavior === "same") return "Same as RX";
    if (memory.transmit_behavior === "disabled") return "Disabled";
    if (memory.transmit_behavior === "offset" && memory.offset_hz !== null) {
      return offsetSummary(memory.offset_hz);
    }
    if (memory.transmit_frequency_hz !== null) return mhz(memory.transmit_frequency_hz);
    return "-";
  }

  function channelTxSummary(channel: ChannelRecord): string {
    if (channel.transmit_behavior === "same") return "Same as RX";
    if (channel.transmit_behavior === "disabled") return "Disabled";
    if (channel.transmit_behavior === "offset" && channel.offset_hz !== null) {
      return offsetSummary(channel.offset_hz);
    }
    if (channel.transmit_frequency_hz !== null) return mhz(channel.transmit_frequency_hz);
    return "-";
  }

  function diagnosticClass(diagnostic: Diagnostic): string {
    return `diagnostic diagnostic--${diagnostic.severity}`;
  }

  function channelStatus(channel: ChannelRecord): string {
    if (plan?.memories.some((memory) => memory.source_channel_id === channel.id)) {
      return "Included";
    }
    if (plan?.omitted_channels.some((item) => item.channel_id === channel.id)) {
      return "Omitted";
    }
    return "Not selected";
  }
</script>

<svelte:head>
  <title>RigManifest</title>
  <meta
    name="description"
    content="Compile operator intent into capability-aware radio configurations."
  />
</svelte:head>

<div class="workbench-shell">
  <aside class="app-sidebar">
    <div class="sidebar-brand">
      <div class="brand-monogram" aria-hidden="true">RM</div>
      <div>
        <strong>RigManifest</strong>
        <span>Configuration compiler</span>
      </div>
    </div>

    <nav class="sidebar-nav" aria-label="Workspace sections">
      <a class="active" href="#plan-workspace">
        <span>Compile plan</span>
      </a>
      <a href="#diagnostics">
        <span>Diagnostics</span>
        {#if plan}<small>{plan.diagnostics.length}</small>{/if}
      </a>
      <a href="#channel-library">
        <span>Channel library</span>
        {#if plan}<small>{plan.channel_library.length}</small>{/if}
      </a>
    </nav>

    <div class="sidebar-spacer"></div>

    <div class="sidebar-connection">
      <span
        class:attention={Boolean(failure) || (plan?.summary.errors ?? 0) > 0}
        class="connection-dot"
      ></span>
      <div>
        <strong>
          {#if busy}
            Compiling
          {:else if failure}
            Core unavailable
          {:else if (plan?.summary.errors ?? 0) > 0}
            Review required
          {:else}
            Core connected
          {/if}
        </strong>
        <span>Compiler {plan?.compiler_version ?? "-"}</span>
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

  <main class="workspace" id="plan-workspace">
    <header class="workspace-header">
      <div>
        <p class="workspace-kicker">Profile workspace</p>
        <h1>Home configuration</h1>
        <p>Compile canonical operator intent for a specific radio.</p>
      </div>
      {#if plan}
        <div class:attention={plan.summary.errors > 0} class="review-status">
          <span></span>
          {plan.summary.errors > 0 ? "Review required" : "Ready to export"}
        </div>
      {/if}
    </header>

    <section class="compile-toolbar" aria-label="Compile controls">
      <label>
        <span>Profile</span>
        <select bind:value={profileId} disabled={busy || exporting}>
          <option value="home">Home</option>
        </select>
      </label>
      <label>
        <span>Target radio</span>
        <select bind:value={targetId} disabled={busy || exporting}>
          <option value="yaesu-vx6r">Yaesu VX-6R - USA</option>
        </select>
      </label>
      <div class="toolbar-spacer"></div>
      <button class="button button--secondary" onclick={exportCsv} disabled={!plan || busy || exporting}>
        {exporting ? "Exporting..." : "Export CHIRP CSV"}
      </button>
      <button class="button button--primary" onclick={runCompile} disabled={busy || exporting}>
        {busy ? "Compiling..." : "Compile plan"}
      </button>
    </section>

    {#if failure}
      <div class="banner banner--error" role="alert">
        <strong>Compiler connection failed.</strong>
        <span>{failure}</span>
      </div>
    {/if}

    {#if exportedPath}
      <div class="banner banner--success" role="status">
        <strong>CSV exported.</strong>
        <span>{exportedPath}</span>
      </div>
    {/if}

    {#if plan}
      <div class="compile-summary" aria-label="Compilation summary">
        <div><strong>{plan.summary.included}</strong><span>Included</span></div>
        <div><strong>{plan.summary.omitted}</strong><span>Omitted</span></div>
        <div class:has-issues={plan.summary.warnings > 0}>
          <strong>{plan.summary.warnings}</strong><span>Warnings</span>
        </div>
        <div class:has-errors={plan.summary.errors > 0}>
          <strong>{plan.summary.errors}</strong><span>Errors</span>
        </div>
        <p>Canonical channels remain unchanged; target-specific compromises stay visible.</p>
      </div>

      <div class="plan-layout">
        <section class="workspace-panel memory-panel" aria-labelledby="memory-plan-heading">
          <div class="panel-heading">
            <div>
              <p class="section-label">Compiled output</p>
              <h2 id="memory-plan-heading">{plan.target.model} memory plan</h2>
            </div>
            <span class="schema-label">Schema v{plan.schema_version}</span>
          </div>

          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th scope="col">Memory</th>
                  <th scope="col">Label</th>
                  <th scope="col">Receive</th>
                  <th scope="col">Transmit</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Groups</th>
                </tr>
              </thead>
              <tbody>
                {#each plan.memories as memory (memory.source_channel_id)}
                  <tr>
                    <td class="memory-number">{memory.memory_number.toString().padStart(2, "0")}</td>
                    <td>
                      <strong class="radio-label">{memory.target_name}</strong>
                      <small>{memory.source_channel_id}</small>
                    </td>
                    <td class="frequency">{mhz(memory.receive_frequency_hz)}</td>
                    <td>{txSummary(memory)}</td>
                    <td>{memory.mode}</td>
                    <td>{memory.bank_assignments.join(", ") || "-"}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>

        <aside class="workspace-panel inspector" id="diagnostics" aria-labelledby="inspector-heading">
          <div class="panel-heading">
            <div>
              <p class="section-label">Target adaptation</p>
              <h2 id="inspector-heading">Plan inspector</h2>
            </div>
          </div>

          <dl class="inspector-facts">
            <div><dt>Memory use</dt><dd>{plan.capacity.used} of {plan.capacity.capacity}</dd></div>
            <div><dt>Compatible candidates</dt><dd>{plan.capacity.compatible_candidates}</dd></div>
            <div><dt>Capacity omissions</dt><dd>{plan.capacity.omitted_for_capacity}</dd></div>
            <div><dt>Target</dt><dd>{plan.target.manufacturer} {plan.target.model}</dd></div>
          </dl>

          <div class="inspector-section-heading">
            <h3>Diagnostics</h3>
            <span>{plan.diagnostics.length}</span>
          </div>

          <div class="diagnostic-list">
            {#each plan.diagnostics as diagnostic, index (`${diagnostic.code}-${diagnostic.channel_id}-${index}`)}
              <article class={diagnosticClass(diagnostic)}>
                <div class="diagnostic-meta">
                  <span>{diagnostic.severity}</span>
                  <code>{diagnostic.code}</code>
                </div>
                <p>{diagnostic.message}</p>
                {#if diagnostic.channel_id}<small>{diagnostic.channel_id}</small>{/if}
              </article>
            {/each}
          </div>
        </aside>
      </div>

      <section class="workspace-panel library-panel" id="channel-library" aria-labelledby="library-heading">
        <div class="panel-heading">
          <div>
            <p class="section-label">Source of truth</p>
            <h2 id="library-heading">Canonical channel library</h2>
          </div>
          <span class="schema-label">{plan.channel_library.length} channels</span>
        </div>

        <div class="table-wrap">
          <table class="data-table library-table">
            <thead>
              <tr>
                <th scope="col">Status</th>
                <th scope="col">Channel</th>
                <th scope="col">Receive</th>
                <th scope="col">Transmit intent</th>
                <th scope="col">Priority</th>
                <th scope="col">Tags</th>
              </tr>
            </thead>
            <tbody>
              {#each plan.channel_library as channel (channel.id)}
                <tr>
                  <td>
                    <span
                      class:status--omitted={channelStatus(channel) === "Omitted"}
                      class="channel-status"
                    >{channelStatus(channel)}</span>
                  </td>
                  <td><strong>{channel.name}</strong><small>{channel.id}</small></td>
                  <td class="frequency">{mhz(channel.receive_frequency_hz)}</td>
                  <td>{channelTxSummary(channel)}</td>
                  <td class="priority">{channel.priority}</td>
                  <td>{channel.tags.join(", ")}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {:else if busy}
      <section class="workspace-panel loading-panel" aria-live="polite">
        <span class="loading-indicator"></span>
        <div><strong>Compiling Home</strong><p>Adapting intent for the Yaesu VX-6R.</p></div>
      </section>
    {/if}
  </main>
</div>
