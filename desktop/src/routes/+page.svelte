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

  let profileId = $state("home");
  let targetId = $state("yaesu-vx6r");
  let plan = $state<CompileResult | null>(null);
  let busy = $state(false);
  let exporting = $state(false);
  let failure = $state("");
  let exportedPath = $state("");

  onMount(() => {
    void runCompile();
  });

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

  function txSummary(memory: CompiledMemory): string {
    if (memory.transmit_behavior === "same") return "Same as RX";
    if (memory.transmit_behavior === "disabled") return "Disabled";
    if (memory.transmit_behavior === "offset" && memory.offset_hz !== null) {
      const sign = memory.offset_hz > 0 ? "+" : "−";
      return `${sign}${(Math.abs(memory.offset_hz) / 1_000_000).toFixed(3)} MHz`;
    }
    if (memory.transmit_frequency_hz !== null) return mhz(memory.transmit_frequency_hz);
    return "—";
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

<div class="app-shell">
  <header class="topbar">
    <div class="brand-mark" aria-hidden="true"><span>RM</span></div>
    <div class="brand-copy">
      <p class="eyebrow">Radio configuration compiler</p>
      <h1>RigManifest</h1>
    </div>
    <div class:status-attention={(plan?.summary.errors ?? 0) > 0} class="core-status">
      <span class="status-dot"></span>
      {#if busy}
        Compiling
      {:else if failure}
        Core unavailable
      {:else if (plan?.summary.errors ?? 0) > 0}
        Review required
      {:else}
        Core connected
      {/if}
    </div>
  </header>

  <main>
    <section class="control-panel" aria-labelledby="compile-heading">
      <div>
        <p class="section-kicker">Compile intent</p>
        <h2 id="compile-heading">Build a target-specific plan</h2>
        <p class="section-description">
          Canonical channels stay unchanged. Target compromises remain visible.
        </p>
      </div>

      <div class="controls">
        <label>
          <span>Profile</span>
          <select bind:value={profileId} disabled={busy || exporting}>
            <option value="home">Home</option>
          </select>
        </label>
        <label>
          <span>Target radio</span>
          <select bind:value={targetId} disabled={busy || exporting}>
            <option value="yaesu-vx6r">Yaesu VX-6R · USA</option>
          </select>
        </label>
        <button class="button button--primary" onclick={runCompile} disabled={busy || exporting}>
          {busy ? "Compiling…" : "Compile plan"}
        </button>
        <button
          class="button button--secondary"
          onclick={exportCsv}
          disabled={!plan || busy || exporting}
        >
          {exporting ? "Exporting…" : "Export CHIRP CSV"}
        </button>
      </div>
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
      <section class="summary-grid" aria-label="Compilation summary">
        <article class="metric-card metric-card--accent">
          <span>Included</span>
          <strong>{plan.summary.included}</strong>
          <small>{plan.capacity.used} of {plan.capacity.capacity} memories</small>
        </article>
        <article class="metric-card">
          <span>Omitted</span>
          <strong>{plan.summary.omitted}</strong>
          <small>{plan.capacity.omitted_for_capacity} due to capacity</small>
        </article>
        <article class="metric-card metric-card--warning">
          <span>Warnings</span>
          <strong>{plan.summary.warnings}</strong>
          <small>Representable compromises</small>
        </article>
        <article class="metric-card metric-card--error">
          <span>Errors</span>
          <strong>{plan.summary.errors}</strong>
          <small>Safety or required intent</small>
        </article>
      </section>

      <div class="workspace-grid">
        <section class="panel panel--wide" aria-labelledby="memory-plan-heading">
          <div class="panel-heading">
            <div>
              <p class="section-kicker">Compiled output</p>
              <h2 id="memory-plan-heading">{plan.target.model} memory plan</h2>
            </div>
            <span class="schema-chip">Schema v{plan.schema_version}</span>
          </div>

          <div class="table-wrap">
            <table>
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
                    <td class="memory-number">{memory.memory_number}</td>
                    <td>
                      <strong class="radio-label">{memory.target_name}</strong>
                      <small>{memory.source_channel_id}</small>
                    </td>
                    <td class="frequency">{mhz(memory.receive_frequency_hz)}</td>
                    <td>{txSummary(memory)}</td>
                    <td><span class="mode-chip">{memory.mode}</span></td>
                    <td>{memory.bank_assignments.join(", ") || "—"}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel diagnostics-panel" aria-labelledby="diagnostics-heading">
          <div class="panel-heading">
            <div>
              <p class="section-kicker">Explainability</p>
              <h2 id="diagnostics-heading">Diagnostics</h2>
            </div>
            <span class="count-chip">{plan.diagnostics.length}</span>
          </div>

          <div class="diagnostic-list">
            {#each plan.diagnostics as diagnostic, index (`${diagnostic.code}-${diagnostic.channel_id}-${index}`)}
              <article class={diagnosticClass(diagnostic)}>
                <div class="diagnostic-meta">
                  <span>{diagnostic.severity}</span>
                  <code>{diagnostic.code}</code>
                </div>
                <p>{diagnostic.message}</p>
                {#if diagnostic.channel_id}
                  <small>{diagnostic.channel_id}</small>
                {/if}
              </article>
            {/each}
          </div>
        </section>
      </div>

      <section class="panel library-panel" aria-labelledby="library-heading">
        <div class="panel-heading">
          <div>
            <p class="section-kicker">Source of truth</p>
            <h2 id="library-heading">Canonical channel library</h2>
          </div>
          <span class="count-chip">{plan.channel_library.length}</span>
        </div>

        <div class="channel-grid">
          {#each plan.channel_library as channel (channel.id)}
            <article class="channel-card">
              <div class="channel-card__topline">
                <span class:outcome-omitted={channelStatus(channel) === "Omitted"} class="outcome-chip">
                  {channelStatus(channel)}
                </span>
                <span class="priority-chip">{channel.priority}</span>
              </div>
              <h3>{channel.name}</h3>
              <p class="frequency">{mhz(channel.receive_frequency_hz)}</p>
              <div class="tag-list">
                {#each channel.tags as tag}
                  <span>{tag}</span>
                {/each}
              </div>
            </article>
          {/each}
        </div>
      </section>
    {:else if busy}
      <section class="loading-panel" aria-live="polite">
        <span class="loading-pulse"></span>
        <p>Compiling the Home profile for the VX-6R…</p>
      </section>
    {/if}
  </main>

  <footer>
    <span>Compiler {plan?.compiler_version ?? "—"}</span>
    <span>Intent in. Explainable radio plans out.</span>
  </footer>
</div>
