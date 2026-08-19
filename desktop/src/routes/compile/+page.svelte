<script lang="ts">
  import { onMount } from "svelte";

  import {
    chooseImageOutputPath,
    compileSelection,
    loadCatalog,
    loadDefaultFrequencyPlan,
    loadRadioInventory,
    saveDefaultFrequencyPlan,
  } from "$lib/api";
  import {
    memoryTxSummary,
    mhz,
    powerSummary,
    scanSummary,
    signalingSummary,
    tuningStepSummary,
  } from "$lib/format";
  import type {
    CompileConfiguration,
    CompileResult,
    Diagnostic,
    ProfileRecord,
    RadioInstance,
    WorkspaceCatalog,
  } from "$lib/types";

  let catalog = $state<WorkspaceCatalog | null>(null);
  let radios = $state<RadioInstance[]>([]);
  let radioId = $state("");
  let selectedProfileIds = $state<string[]>([]);
  let additionalSetIds = $state<string[]>([]);
  let additionalDefinitionIds = $state<string[]>([]);
  let selectedPlanId = $state<string | null>(null);
  let plan = $state<CompileResult | null>(null);
  let busy = $state(false);
  let exporting = $state(false);
  let failure = $state("");
  let exportedPath = $state("");
  let definitionSearch = $state("");

  let selectedRadio = $derived(radios.find((item) => item.id === radioId) ?? null);
  let selectedProfiles = $derived(
    (catalog?.profiles ?? []).filter((profile) => selectedProfileIds.includes(profile.id)),
  );
  let filteredDefinitions = $derived(
    (catalog?.frequency_definitions ?? []).filter((definition) => {
      const query = definitionSearch.trim().toLocaleLowerCase();
      return !query || `${definition.name} ${definition.receive_frequency_hz}`.toLocaleLowerCase().includes(query);
    }),
  );
  let hasSelection = $derived(
    selectedProfileIds.length + additionalSetIds.length + additionalDefinitionIds.length > 0,
  );

  onMount(async () => {
    try {
      catalog = await loadCatalog();
      radios = loadRadioInventory();
      radioId = radios[0]?.id ?? "";
      const home = catalog.profiles.find((profile) => profile.id === "home") ?? catalog.profiles[0];
      selectedProfileIds = home ? [home.id] : [];
      selectedPlanId = loadDefaultFrequencyPlan();
    } catch (error) {
      failure = errorMessage(error);
    }
  });

  function configuration(): CompileConfiguration {
    return {
      memoryStart: selectedRadio?.memoryStart ?? 1,
      mapSetsToBanks: selectedRadio?.mapSetsToBanks ?? true,
      useFactorySets: false,
      additionalFrequencySetIds: additionalSetIds,
      additionalFrequencyDefinitionIds: additionalDefinitionIds,
      advisoryPlanId: selectedPlanId,
    };
  }

  async function runCompile(): Promise<void> {
    if (!catalog || !selectedRadio || !hasSelection) return;
    busy = true;
    failure = "";
    exportedPath = "";
    try {
      plan = await compileSelection(
        selectedRadio.id,
        null,
        selectedProfiles,
        configuration(),
        catalog,
      );
    } catch (error) {
      plan = null;
      failure = errorMessage(error);
    } finally {
      busy = false;
    }
  }

  async function exportImage(): Promise<void> {
    if (!catalog || !selectedRadio || !plan) return;
    const label = selectedProfiles.map((profile) => profile.id).join("-") || "custom";
    const outputPath = await chooseImageOutputPath(label, selectedRadio);
    if (!outputPath) return;
    exporting = true;
    failure = "";
    try {
      plan = await compileSelection(
        selectedRadio.id,
        outputPath,
        selectedProfiles,
        configuration(),
        catalog,
      );
      exportedPath = plan.image_path ?? outputPath;
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      exporting = false;
    }
  }

  function toggleProfile(profileId: string, checked: boolean): void {
    selectedProfileIds = checked
      ? [...selectedProfileIds, profileId]
      : selectedProfileIds.filter((id) => id !== profileId);
    markStale();
  }

  function toggleAdditionalSet(setId: string, checked: boolean): void {
    additionalSetIds = checked
      ? [...additionalSetIds, setId]
      : additionalSetIds.filter((id) => id !== setId);
    markStale();
  }

  function toggleAdditionalDefinition(definitionId: string, checked: boolean): void {
    additionalDefinitionIds = checked
      ? [...additionalDefinitionIds, definitionId]
      : additionalDefinitionIds.filter((id) => id !== definitionId);
    markStale();
  }

  function selectPlan(planId: string): void {
    selectedPlanId = planId || null;
    void saveDefaultFrequencyPlan(selectedPlanId).catch((error) => failure = errorMessage(error));
    markStale();
  }

  function markStale(): void {
    plan = null;
    exportedPath = "";
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
  <meta name="description" content="Compile profiles and additional frequency intent for a radio." />
</svelte:head>

<main class="workspace">
  <header class="workspace-header">
    <div>
      <p class="workspace-kicker">Programming workflow</p>
      <h1>Compile & export</h1>
      <p>Choose a radio, combine profiles with one-off additions, then review the exact memory plan.</p>
    </div>
    {#if plan}<div class:attention={plan.summary.errors > 0} class="review-status"><span></span>{plan.summary.errors > 0 ? "Review required" : "Compiled and ready"}</div>{/if}
  </header>

  <section class="compile-toolbar" aria-label="Compile controls">
    <label><span>Target radio</span><select bind:value={radioId} onchange={markStale} disabled={busy || exporting}>{#each radios as radio}<option value={radio.id}>{radio.name}</option>{/each}</select></label>
    <label><span>Additional whole-build plan check</span><select value={selectedPlanId ?? ""} onchange={(event) => selectPlan(event.currentTarget.value)} disabled={busy || exporting}><option value="">Use profile plans only</option>{#each catalog?.frequency_plans ?? [] as frequencyPlan}<option value={frequencyPlan.id}>{frequencyPlan.name} · {frequencyPlan.jurisdiction}</option>{/each}</select></label>
    <div class="toolbar-spacer"></div>
    <button class="button button--primary" onclick={runCompile} disabled={busy || exporting || !hasSelection || !selectedRadio}>{busy ? "Compiling..." : "Compile plan"}</button>
  </section>

  {#if failure}<div class="banner banner--error" role="alert"><strong>Compilation failed.</strong><span>{failure}</span></div>{/if}
  {#if exportedPath}<div class="banner banner--success" role="status"><strong>Radio image exported.</strong><span>{exportedPath}</span></div>{/if}
  {#if catalog && radios.length === 0}<div class="banner" role="status"><strong>Add a radio first.</strong><span>Import a fresh CHIRP IMG on the My Radios page before compiling.</span></div>{/if}

  {#if catalog && selectedRadio}
    <section class="workspace-panel set-picker" aria-labelledby="profile-picker-heading">
      <div class="panel-heading"><div><p class="section-label">Reusable loadouts</p><h2 id="profile-picker-heading">Profiles</h2></div><span class="schema-label">{selectedProfileIds.length} selected</span></div>
      <div class="set-picker-grid profile-picker-grid">
        {#each catalog.profiles as profile (profile.id)}
          <label class="set-choice profile-choice"><input type="checkbox" checked={selectedProfileIds.includes(profile.id)} onchange={(event) => toggleProfile(profile.id, event.currentTarget.checked)} /><span><strong>{profile.name}</strong><small>{profile.frequency_set_ids.length} sets · {profile.frequency_definition_ids.length} individual</small></span>{#if profile.frequency_plan_id}<b>{catalog.frequency_plans.find((plan) => plan.id === profile.frequency_plan_id)?.jurisdiction ?? profile.frequency_plan_id}</b>{/if}</label>
        {:else}
          <p class="empty-copy">No profiles yet. Add one on the Profiles page or compile one-off selections below.</p>
        {/each}
      </div>
    </section>

    <section class="workspace-panel compile-additions" aria-labelledby="additional-selection-heading">
      <div class="panel-heading"><div><p class="section-label">One-off additions</p><h2 id="additional-selection-heading">Additional selections</h2></div><span class="schema-label">{additionalSetIds.length + additionalDefinitionIds.length} selected</span></div>
      <div class="profile-source-grid compile-source-grid">
        <section><div class="subsection-heading"><div><p class="section-label">Collections</p><h3>Frequency sets and imported banks</h3></div></div><div class="selection-list compact-selection-list">{#each catalog.frequency_sets as frequencySet (frequencySet.id)}<label class="selection-row"><input type="checkbox" checked={additionalSetIds.includes(frequencySet.id)} onchange={(event) => toggleAdditionalSet(frequencySet.id, event.currentTarget.checked)} /><span><strong>{frequencySet.name}</strong><small>{frequencySet.members.length} definitions · {frequencySet.read_only ? "Preset" : "My set"}</small></span></label>{/each}</div></section>
        <section><div class="subsection-heading"><div><p class="section-label">Individual additions</p><h3>Frequency definitions</h3></div></div><label class="selection-search"><span>Find a definition</span><input bind:value={definitionSearch} placeholder="Name or frequency" /></label><div class="selection-list compact-selection-list">{#each filteredDefinitions as definition (definition.id)}<label class="selection-row"><input type="checkbox" checked={additionalDefinitionIds.includes(definition.id)} onchange={(event) => toggleAdditionalDefinition(definition.id, event.currentTarget.checked)} /><span><strong>{definition.name}</strong><small>{mhz(definition.receive_frequency_hz)} · {definition.read_only ? "Preset" : "User"}</small></span></label>{/each}</div></section>
      </div>
      <div class="compile-options"><span>The source image's radio settings and factory areas remain untouched.</span><span>Plan advice can warn, but it never removes or blocks a memory.</span></div>
    </section>
  {/if}

  {#if plan}
    <div class="compile-summary" aria-label="Compilation summary"><div><strong>{plan.summary.programmed}</strong><span>Programmed</span></div><div><strong>{plan.summary.factory_provided}</strong><span>Factory-provided</span></div><div><strong>{plan.summary.omitted}</strong><span>Omitted</span></div><div class:has-issues={plan.summary.warnings > 0}><strong>{plan.summary.warnings}</strong><span>Warnings</span></div><div class:has-errors={plan.summary.errors > 0}><strong>{plan.summary.errors}</strong><span>Errors</span></div><p>Warnings remain advisory; radio capability errors explain any omitted memories.</p></div>

    {#if plan.factory_sets.length > 0}<section class="factory-coverage" aria-label="Factory-provided frequency sets">{#each plan.factory_sets as coverage (coverage.frequency_set_id)}<article><div><p class="section-label">Already on this model</p><strong>{coverage.frequency_set_name}</strong></div><span class="record-badge badge--preset">{coverage.interface_label}</span><small>{coverage.definition_count} definitions · CHIRP editing {coverage.chirp_editing}</small></article>{/each}</section>{/if}

    <div class="plan-layout">
      <section class="workspace-panel memory-panel" aria-labelledby="memory-plan-heading">
        <div class="panel-heading"><div><p class="section-label">Compiled output</p><h2 id="memory-plan-heading">{plan.target.model} memory plan</h2></div><div class="panel-actions"><span class="schema-label">Schema v{plan.schema_version}</span><button class="button button--primary" onclick={exportImage} disabled={exporting}>{exporting ? "Exporting..." : "Export CHIRP IMG"}</button></div></div>
        <div class="table-wrap" role="region" aria-label="Compiled frequency table" tabindex="0"><table class="data-table"><thead><tr><th scope="col">Memory</th><th scope="col">Label</th><th scope="col">Receive</th><th scope="col">Transmit</th><th scope="col">TX access</th><th scope="col">RX squelch</th><th scope="col">Mode</th><th scope="col">Step</th><th scope="col">Power / scan</th><th scope="col">Banks</th><th scope="col">Sources</th></tr></thead><tbody>{#each plan.memories as memory (memory.source_frequency_definition_id)}<tr><td class="memory-number">{memory.memory_number.toString().padStart(2, "0")}</td><td><strong class="radio-label">{memory.target_name}</strong><small>{memory.source_frequency_definition_id}</small></td><td class="frequency">{mhz(memory.receive_frequency_hz)}</td><td>{memoryTxSummary(memory)}</td><td>{signalingSummary(memory.transmit_access)}</td><td>{signalingSummary(memory.receive_squelch)}</td><td>{memory.mode}</td><td>{tuningStepSummary(memory.tuning_step_hz)}</td><td><strong>{powerSummary(memory)}</strong><small>{scanSummary(memory.scan_skip)}</small></td><td>{memory.bank_assignments.join(", ") || "—"}</td><td><strong>{memory.source_profile_ids.join(", ") || (memory.selected_directly ? "Direct" : "—")}</strong><small>{memory.source_frequency_set_ids.join(", ")}</small></td></tr>{/each}</tbody></table></div>
      </section>

      <aside class="workspace-panel inspector" aria-labelledby="inspector-heading"><div class="panel-heading"><div><p class="section-label">Target and plan review</p><h2 id="inspector-heading">Plan inspector</h2></div></div><dl class="inspector-facts"><div><dt>Memory use</dt><dd>{plan.capacity.used} of {plan.capacity.capacity}</dd></div><div><dt>Profiles</dt><dd>{plan.profiles.length}</dd></div><div><dt>Factory sets</dt><dd>{plan.summary.factory_sets}</dd></div><div><dt>Target</dt><dd>{plan.target.manufacturer} {plan.target.model}</dd></div></dl><div class="inspector-section-heading"><h3>Diagnostics</h3><span>{plan.diagnostics.length}</span></div><!-- svelte-ignore a11y_no_noninteractive_tabindex --><div class="diagnostic-list" role="region" aria-label="Compilation diagnostics" tabindex="0">{#each plan.diagnostics as diagnostic, index (`${diagnostic.code}-${diagnosticSubject(diagnostic)}-${index}`)}<article class={diagnosticClass(diagnostic)}><div class="diagnostic-meta"><span>{diagnostic.severity}</span><code>{diagnostic.code}</code></div><p>{diagnostic.message}</p>{#if diagnosticSubject(diagnostic)}<small>{diagnosticSubject(diagnostic)}</small>{/if}</article>{/each}</div></aside>
    </div>
  {:else if busy || !catalog}
    <section class="workspace-panel loading-panel" aria-live="polite"><span class="loading-indicator"></span><div><strong>{busy ? "Compiling selection" : "Preparing compiler"}</strong><p>Resolving profiles, sets, definitions, and target capabilities.</p></div></section>
  {:else}
    <section class="workspace-panel compile-empty"><p class="section-label">No compiled output yet</p><h2>Ready when you are</h2><p>Compile creates the reviewable memory plan. Export becomes available with that result.</p></section>
  {/if}
</main>
