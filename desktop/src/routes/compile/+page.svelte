<script lang="ts">
  import { onMount } from "svelte";

  import { chooseCsvOutputPath, compileProfile, loadCatalog } from "$lib/api";
  import { memoryTxSummary, mhz } from "$lib/format";
  import { loadRadioInventory } from "$lib/radios";
  import type {
    CompileConfiguration,
    CompileResult,
    Diagnostic,
    RadioInstance,
    WorkspaceCatalog,
  } from "$lib/types";

  let catalog = $state<WorkspaceCatalog | null>(null);
  let radios = $state<RadioInstance[]>([]);
  let profileId = $state("home");
  let radioId = $state("");
  let selectedSetIds = $state<string[]>([]);
  let useFactorySets = $state(true);
  let plan = $state<CompileResult | null>(null);
  let busy = $state(false);
  let exporting = $state(false);
  let failure = $state("");
  let exportedPath = $state("");

  let selectedRadio = $derived(radios.find((item) => item.id === radioId) ?? null);
  let selectedModel = $derived(
    catalog?.radio_models.find((item) => item.id === selectedRadio?.radioModelId) ?? null,
  );

  onMount(async () => {
    try {
      catalog = await loadCatalog();
      radios = loadRadioInventory();
      radioId = radios[0]?.id ?? "";
      const profile = catalog.profiles.find((item) => item.id === profileId);
      const availableSetIds = new Set(catalog.frequency_sets.map((item) => item.id));
      selectedSetIds = (profile?.frequency_set_ids ?? []).filter((item) =>
        availableSetIds.has(item),
      );
      if (selectedSetIds.length === 0 && catalog.frequency_sets[0]) {
        selectedSetIds = [catalog.frequency_sets[0].id];
      }
      await runCompile();
    } catch (error) {
      failure = errorMessage(error);
    }
  });

  function currentConfiguration(): CompileConfiguration {
    return {
      memoryStart: selectedRadio?.memoryStart ?? selectedModel?.memory_start ?? 1,
      mapSetsToBanks: selectedRadio?.mapSetsToBanks ?? true,
      useFactorySets,
      frequencySetIds: selectedSetIds,
    };
  }

  async function runCompile(): Promise<void> {
    if (!catalog || !selectedRadio || selectedSetIds.length === 0) return;
    busy = true;
    failure = "";
    exportedPath = "";
    try {
      plan = await compileProfile(
        profileId,
        selectedRadio.radioModelId,
        null,
        currentConfiguration(),
        catalog,
      );
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      busy = false;
    }
  }

  async function exportCsv(): Promise<void> {
    if (!catalog || !selectedRadio || selectedSetIds.length === 0) return;
    failure = "";
    const outputPath = await chooseCsvOutputPath(profileId, selectedRadio.radioModelId);
    if (!outputPath) return;

    exporting = true;
    try {
      plan = await compileProfile(
        profileId,
        selectedRadio.radioModelId,
        outputPath,
        currentConfiguration(),
        catalog,
      );
      exportedPath = outputPath;
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      exporting = false;
    }
  }

  function toggleSet(setId: string, checked: boolean): void {
    if (checked) {
      if (!selectedSetIds.includes(setId)) selectedSetIds = [...selectedSetIds, setId];
    } else {
      selectedSetIds = selectedSetIds.filter((item) => item !== setId);
    }
    plan = null;
  }

  function resetProfileSets(): void {
    const profile = catalog?.profiles.find((item) => item.id === profileId);
    const availableSetIds = new Set(
      catalog?.frequency_sets.map((item) => item.id) ?? [],
    );
    selectedSetIds = (profile?.frequency_set_ids ?? []).filter((item) =>
      availableSetIds.has(item),
    );
    plan = null;
  }

  function isFactorySet(setId: string): string | null {
    return selectedModel?.factory_frequency_sets.find(
      (item) => item.frequency_set_id === setId,
    )?.interface_label ?? null;
  }

  function diagnosticClass(diagnostic: Diagnostic): string {
    return `diagnostic diagnostic--${diagnostic.severity}`;
  }

  function diagnosticSubject(diagnostic: Diagnostic): string | null {
    return diagnostic.frequency_definition_id ?? diagnostic.frequency_set_id;
  }

  function errorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    if (error instanceof Error) return error.message;
    return "The compiler could not be reached.";
  }
</script>

<svelte:head>
  <title>Compile & export · RigManifest</title>
  <meta name="description" content="Compile selected frequency sets for a radio." />
</svelte:head>

<main class="workspace">
  <header class="workspace-header">
    <div>
      <p class="workspace-kicker">Programming workspace</p>
      <h1>Compile & export</h1>
      <p>Choose frequency sets, account for factory-provided sets, then build programmable memories.</p>
    </div>
    {#if plan}
      <div class:attention={plan.summary.errors > 0} class="review-status">
        <span></span>{plan.summary.errors > 0 ? "Review required" : "Ready to export"}
      </div>
    {/if}
  </header>

  <section class="compile-toolbar" aria-label="Compile controls">
    <label>
      <span>Saved profile</span>
      <select bind:value={profileId} onchange={resetProfileSets} disabled={busy || exporting}>
        {#each catalog?.profiles ?? [] as profile}<option value={profile.id}>{profile.name}</option>{/each}
      </select>
    </label>
    <label>
      <span>My radio</span>
      <select bind:value={radioId} disabled={busy || exporting}>
        {#each radios as radio}<option value={radio.id}>{radio.name}</option>{/each}
      </select>
    </label>
    <div class="toolbar-spacer"></div>
    <button class="button button--secondary" onclick={exportCsv} disabled={!plan || busy || exporting}>
      {exporting ? "Exporting..." : "Export CHIRP CSV"}
    </button>
    <button class="button button--primary" onclick={runCompile} disabled={busy || exporting || selectedSetIds.length === 0}>
      {busy ? "Compiling..." : "Compile plan"}
    </button>
  </section>

  {#if failure}
    <div class="banner banner--error" role="alert"><strong>Compiler connection failed.</strong><span>{failure}</span></div>
  {/if}
  {#if exportedPath}
    <div class="banner banner--success" role="status"><strong>CSV exported.</strong><span>{exportedPath}</span></div>
  {/if}

  {#if catalog && selectedRadio && selectedModel}
    <section class="workspace-panel set-picker" aria-labelledby="set-picker-heading">
      <div class="panel-heading">
        <div><p class="section-label">Programming input</p><h2 id="set-picker-heading">Frequency sets</h2></div>
        <span class="schema-label">{selectedSetIds.length} selected</span>
      </div>
      <div class="set-picker-grid">
        {#each catalog.frequency_sets as frequencySet (frequencySet.id)}
          {@const factoryLabel = isFactorySet(frequencySet.id)}
          <label class:factory={Boolean(factoryLabel)} class="set-choice">
            <input
              type="checkbox"
              checked={selectedSetIds.includes(frequencySet.id)}
              onchange={(event) => toggleSet(frequencySet.id, event.currentTarget.checked)}
            />
            <span>
              <strong>{frequencySet.name}</strong>
              <small>{frequencySet.members.length} definitions · {frequencySet.read_only ? "Preset" : "My set"}</small>
            </span>
            {#if factoryLabel}<b>Factory · {factoryLabel}</b>{/if}
          </label>
        {/each}
      </div>
      <div class="compile-options">
        <label><input type="checkbox" bind:checked={useFactorySets} onchange={() => plan = null} /><span>Use verified factory-provided sets instead of programming duplicates</span></label>
        <span>Factory relationships come from the radio model, not frequency matching.</span>
      </div>
    </section>
  {/if}

  {#if plan}
    <div class="compile-summary" aria-label="Compilation summary">
      <div><strong>{plan.summary.programmed}</strong><span>Programmed</span></div>
      <div><strong>{plan.summary.factory_provided}</strong><span>Factory-provided</span></div>
      <div><strong>{plan.summary.omitted}</strong><span>Omitted</span></div>
      <div class:has-issues={plan.summary.warnings > 0}><strong>{plan.summary.warnings}</strong><span>Warnings</span></div>
      <div class:has-errors={plan.summary.errors > 0}><strong>{plan.summary.errors}</strong><span>Errors</span></div>
      <p>Frequency definitions remain unchanged; compilation only creates radio memory assignments.</p>
    </div>

    {#if plan.factory_sets.length > 0}
      <section class="factory-coverage" aria-label="Factory-provided frequency sets">
        {#each plan.factory_sets as coverage (coverage.frequency_set_id)}
          <article>
            <div><p class="section-label">Already on this model</p><strong>{coverage.frequency_set_name}</strong></div>
            <span class="record-badge badge--preset">{coverage.interface_label}</span>
            <small>{coverage.definition_count} definitions · CHIRP editing {coverage.chirp_editing}</small>
          </article>
        {/each}
      </section>
    {/if}

    <div class="plan-layout">
      <section class="workspace-panel memory-panel" aria-labelledby="memory-plan-heading">
        <div class="panel-heading">
          <div><p class="section-label">Programmable output</p><h2 id="memory-plan-heading">{plan.target.model} memory plan</h2></div>
          <span class="schema-label">Schema v{plan.schema_version}</span>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th scope="col">Memory</th><th scope="col">Label</th><th scope="col">Receive</th><th scope="col">Transmit</th><th scope="col">Mode</th><th scope="col">Source sets</th></tr></thead>
            <tbody>
              {#each plan.memories as memory (memory.source_frequency_definition_id)}
                <tr>
                  <td class="memory-number">{memory.memory_number.toString().padStart(2, "0")}</td>
                  <td><strong class="radio-label">{memory.target_name}</strong><small>{memory.source_frequency_definition_id}</small></td>
                  <td class="frequency">{mhz(memory.receive_frequency_hz)}</td>
                  <td>{memoryTxSummary(memory)}</td>
                  <td>{memory.mode}</td>
                  <td>{memory.source_frequency_set_ids.join(", ")}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <aside class="workspace-panel inspector" aria-labelledby="inspector-heading">
        <div class="panel-heading"><div><p class="section-label">Target adaptation</p><h2 id="inspector-heading">Plan inspector</h2></div></div>
        <dl class="inspector-facts">
          <div><dt>Memory use</dt><dd>{plan.capacity.used} of {plan.capacity.capacity}</dd></div>
          <div><dt>Factory sets</dt><dd>{plan.summary.factory_sets}</dd></div>
          <div><dt>Compatible candidates</dt><dd>{plan.capacity.compatible_candidates}</dd></div>
          <div><dt>Target</dt><dd>{plan.target.manufacturer} {plan.target.model}</dd></div>
        </dl>
        <div class="inspector-section-heading"><h3>Diagnostics</h3><span>{plan.diagnostics.length}</span></div>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex (Scrollable diagnostics need keyboard access.) -->
        <div class="diagnostic-list" role="region" aria-label="Compilation diagnostics" tabindex="0">
          {#each plan.diagnostics as diagnostic, index (`${diagnostic.code}-${diagnosticSubject(diagnostic)}-${index}`)}
            <article class={diagnosticClass(diagnostic)}>
              <div class="diagnostic-meta"><span>{diagnostic.severity}</span><code>{diagnostic.code}</code></div>
              <p>{diagnostic.message}</p>
              {#if diagnosticSubject(diagnostic)}<small>{diagnosticSubject(diagnostic)}</small>{/if}
            </article>
          {/each}
        </div>
      </aside>
    </div>
  {:else if busy || !catalog}
    <section class="workspace-panel loading-panel" aria-live="polite">
      <span class="loading-indicator"></span><div><strong>Preparing compiler</strong><p>Resolving selected sets for your radio.</p></div>
    </section>
  {/if}
</main>
