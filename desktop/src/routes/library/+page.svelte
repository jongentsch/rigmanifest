<script lang="ts">
  import { onMount } from "svelte";

  import { loadCatalog } from "$lib/api";
  import { saveWorkspaceUserCatalog } from "$lib/catalog";
  import { definitionTxSummary, mhz, offsetSummary } from "$lib/format";
  import type {
    FrequencyDefinitionRecord,
    FrequencyPlanRecord,
    FrequencyPlanSegmentRecord,
    FrequencySetMemberRecord,
    FrequencySetRecord,
    SignalingKind,
    SignalingSpec,
    WorkspaceCatalog,
  } from "$lib/types";

  let catalog = $state<WorkspaceCatalog | null>(null);
  let selectedSetId = $state("");
  let selectedDefinitionId = $state("");
  let existingDefinitionId = $state("");
  let failure = $state("");
  let saved = $state(false);

  let selectedSet = $derived(
    catalog?.frequency_sets.find((item) => item.id === selectedSetId) ?? null,
  );
  let selectedDefinitions = $derived(resolveDefinitions(selectedSet, catalog));
  let selectedDefinition = $derived(
    catalog?.frequency_definitions.find(
      (item) => item.id === selectedDefinitionId,
    ) ?? null,
  );
  let availableDefinitions = $derived(
    (catalog?.frequency_definitions ?? []).filter(
      (definition) =>
        !selectedSet?.members.some(
          (member) => member.frequency_definition_id === definition.id,
        ),
    ),
  );
  let planSuggestion = $derived(
    resolvePlanSuggestion(selectedDefinition, catalog?.frequency_plans ?? []),
  );

  onMount(async () => {
    try {
      catalog = await loadCatalog();
      const initialSet =
        catalog.frequency_sets.find((item) => !item.read_only) ??
        catalog.frequency_sets[0] ??
        null;
      selectSet(initialSet?.id ?? "");
    } catch (error) {
      failure = errorMessage(error);
    }
  });

  function resolveDefinitions(
    frequencySet: FrequencySetRecord | null,
    workspace: WorkspaceCatalog | null,
  ): Array<{
    definition: FrequencyDefinitionRecord;
    member: FrequencySetMemberRecord;
  }> {
    if (!frequencySet || !workspace) return [];
    const definitions = new Map(
      workspace.frequency_definitions.map((item) => [item.id, item]),
    );
    return [...frequencySet.members]
      .sort((left, right) => left.position - right.position)
      .flatMap((member) => {
        const definition = definitions.get(member.frequency_definition_id);
        return definition ? [{ definition, member }] : [];
      });
  }

  function selectSet(setId: string): void {
    selectedSetId = setId;
    const frequencySet = catalog?.frequency_sets.find((item) => item.id === setId);
    selectedDefinitionId =
      [...(frequencySet?.members ?? [])].sort(
        (left, right) => left.position - right.position,
      )[0]?.frequency_definition_id ?? "";
    existingDefinitionId = "";
    saved = false;
  }

  function persist(next: WorkspaceCatalog): void {
    catalog = next;
    saveWorkspaceUserCatalog(next);
    saved = true;
  }

  function updateSelectedSet(changes: Partial<FrequencySetRecord>): void {
    if (!catalog || !selectedSet || selectedSet.read_only) return;
    persist({
      ...catalog,
      frequency_sets: catalog.frequency_sets.map((item) =>
        item.id === selectedSetId ? { ...item, ...changes } : item,
      ),
    });
  }

  function addSet(): void {
    if (!catalog) return;
    const frequencySet: FrequencySetRecord = {
      id: uniqueId("set"),
      name: "New frequency set",
      origin: "user",
      read_only: false,
      description: "",
      members: [],
    };
    persist({
      ...catalog,
      frequency_sets: [...catalog.frequency_sets, frequencySet],
    });
    selectSet(frequencySet.id);
    saved = true;
  }

  function removeSet(): void {
    if (!catalog || !selectedSet || selectedSet.read_only) return;
    if (!confirm(`Delete the set “${selectedSet.name}”? Definitions will be kept.`)) {
      return;
    }
    const frequency_sets = catalog.frequency_sets.filter(
      (item) => item.id !== selectedSetId,
    );
    const next = { ...catalog, frequency_sets };
    persist(next);
    const replacement =
      frequency_sets.find((item) => !item.read_only) ?? frequency_sets[0] ?? null;
    selectSet(replacement?.id ?? "");
    saved = true;
  }

  function addDefinition(): void {
    if (!catalog || !selectedSet || selectedSet.read_only) return;
    const definition: FrequencyDefinitionRecord = {
      id: uniqueId("frequency"),
      name: "New frequency",
      origin: "user",
      read_only: false,
      receive_frequency_hz: 146_520_000,
      transmit_behavior: "same",
      transmit_frequency_hz: null,
      offset_hz: null,
      mode: "FM",
      transmit_access: emptySignaling(),
      receive_squelch: emptySignaling(),
      tags: [],
      priority: "normal",
      notes: "",
    };
    const member: FrequencySetMemberRecord = {
      frequency_definition_id: definition.id,
      position: nextPosition(selectedSet),
      channel_designator: null,
    };
    persist({
      ...catalog,
      frequency_definitions: [...catalog.frequency_definitions, definition],
      frequency_sets: catalog.frequency_sets.map((item) =>
        item.id === selectedSetId
          ? { ...item, members: [...item.members, member] }
          : item,
      ),
    });
    selectedDefinitionId = definition.id;
  }

  function addExistingDefinition(): void {
    if (
      !catalog ||
      !selectedSet ||
      selectedSet.read_only ||
      !existingDefinitionId
    ) return;
    const member: FrequencySetMemberRecord = {
      frequency_definition_id: existingDefinitionId,
      position: nextPosition(selectedSet),
      channel_designator: null,
    };
    updateSelectedSet({ members: [...selectedSet.members, member] });
    selectedDefinitionId = existingDefinitionId;
    existingDefinitionId = "";
  }

  function updateMember(
    definitionId: string,
    changes: Partial<FrequencySetMemberRecord>,
  ): void {
    if (!selectedSet || selectedSet.read_only) return;
    updateSelectedSet({
      members: selectedSet.members.map((member) =>
        member.frequency_definition_id === definitionId
          ? { ...member, ...changes }
          : member,
      ),
    });
  }

  function removeMembership(definitionId: string): void {
    if (!selectedSet || selectedSet.read_only) return;
    const members = selectedSet.members
      .filter((member) => member.frequency_definition_id !== definitionId)
      .sort((left, right) => left.position - right.position)
      .map((member, position) => ({ ...member, position }));
    updateSelectedSet({ members });
    selectedDefinitionId = members[0]?.frequency_definition_id ?? "";
  }

  function updateDefinition(
    changes: Partial<FrequencyDefinitionRecord>,
  ): void {
    if (!catalog || !selectedDefinition || selectedDefinition.read_only) return;
    persist({
      ...catalog,
      frequency_definitions: catalog.frequency_definitions.map((item) =>
        item.id === selectedDefinitionId ? { ...item, ...changes } : item,
      ),
    });
  }

  function changeTransmitBehavior(behavior: string): void {
    if (!selectedDefinition) return;
    if (behavior === "offset") {
      updateDefinition({
        transmit_behavior: behavior,
        transmit_frequency_hz: null,
        offset_hz: selectedDefinition.offset_hz ?? 600_000,
      });
    } else if (behavior === "split") {
      updateDefinition({
        transmit_behavior: behavior,
        transmit_frequency_hz:
          selectedDefinition.transmit_frequency_hz ??
          selectedDefinition.receive_frequency_hz,
        offset_hz: null,
      });
    } else {
      updateDefinition({
        transmit_behavior: behavior,
        transmit_frequency_hz: null,
        offset_hz: null,
      });
    }
  }

  function changeSignaling(
    direction: "transmit_access" | "receive_squelch",
    kind: SignalingKind,
  ): void {
    const signaling = emptySignaling();
    signaling.kind = kind;
    if (kind === "ctcss") signaling.ctcss_hz = 100;
    if (kind === "dcs") signaling.dcs_code = 23;
    updateDefinition({ [direction]: signaling });
  }

  function updateSignaling(
    direction: "transmit_access" | "receive_squelch",
    changes: Partial<SignalingSpec>,
  ): void {
    if (!selectedDefinition) return;
    updateDefinition({
      [direction]: { ...selectedDefinition[direction], ...changes },
    });
  }

  function updateFrequency(
    key: "receive_frequency_hz" | "transmit_frequency_hz" | "offset_hz",
    megahertz: number,
  ): void {
    if (!Number.isFinite(megahertz)) return;
    updateDefinition({ [key]: Math.round(megahertz * 1_000_000) });
  }

  function applyPlanOffset(): void {
    const offset = planSuggestion?.segment.suggested_offset_hz;
    if (offset === null || offset === undefined) return;
    updateDefinition({
      transmit_behavior: "offset",
      transmit_frequency_hz: null,
      offset_hz: offset,
    });
  }

  function resolvePlanSuggestion(
    definition: FrequencyDefinitionRecord | null,
    plans: FrequencyPlanRecord[],
  ): { plan: FrequencyPlanRecord; segment: FrequencyPlanSegmentRecord } | null {
    if (!definition) return null;
    for (const plan of plans) {
      const segment = plan.segments.find(
        (item) =>
          definition.receive_frequency_hz >= item.lower_hz &&
          definition.receive_frequency_hz <= item.upper_hz,
      );
      if (segment) return { plan, segment };
    }
    return null;
  }

  function rasterStatus(
    definition: FrequencyDefinitionRecord,
    segment: FrequencyPlanSegmentRecord,
  ): boolean | null {
    if (segment.raster_anchor_hz === null || segment.raster_spacing_hz === null) {
      return null;
    }
    return (
      (definition.receive_frequency_hz - segment.raster_anchor_hz) %
        segment.raster_spacing_hz ===
      0
    );
  }

  function planOffsetApplied(
    definition: FrequencyDefinitionRecord,
    segment: FrequencyPlanSegmentRecord,
  ): boolean {
    return (
      definition.transmit_behavior === "offset" &&
      definition.offset_hz === segment.suggested_offset_hz
    );
  }

  function deleteDefinition(): void {
    if (!catalog || !selectedDefinition || selectedDefinition.read_only) return;
    if (
      !confirm(
        `Delete “${selectedDefinition.name}” from every user set? This cannot be undone.`,
      )
    ) return;
    const definitionId = selectedDefinition.id;
    const next: WorkspaceCatalog = {
      ...catalog,
      frequency_definitions: catalog.frequency_definitions.filter(
        (item) => item.id !== definitionId,
      ),
      frequency_sets: catalog.frequency_sets.map((frequencySet) => ({
        ...frequencySet,
        members: frequencySet.members
          .filter((member) => member.frequency_definition_id !== definitionId)
          .map((member, position) => ({ ...member, position })),
      })),
    };
    persist(next);
    selectedDefinitionId =
      next.frequency_sets
        .find((item) => item.id === selectedSetId)
        ?.members[0]?.frequency_definition_id ?? "";
  }

  function nextPosition(frequencySet: FrequencySetRecord): number {
    return frequencySet.members.length === 0
      ? 0
      : Math.max(...frequencySet.members.map((item) => item.position)) + 1;
  }

  function uniqueId(kind: string): string {
    return `user-${kind}-${crypto.randomUUID()}`;
  }

  function emptySignaling(): SignalingSpec {
    return {
      kind: "none",
      ctcss_hz: null,
      dcs_code: null,
      dcs_polarity: "N",
    };
  }

  function errorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    if (error instanceof Error) return error.message;
    return "The frequency catalog could not be loaded.";
  }
</script>

<svelte:head>
  <title>Frequency library · RigManifest</title>
</svelte:head>

<main class="workspace">
  <header class="workspace-header">
    <div>
      <p class="workspace-kicker">Shared catalog</p>
      <h1>Frequency library</h1>
      <p>Build your own sets from shared definitions. Presets remain read-only.</p>
    </div>
    <button class="button button--primary" onclick={addSet} disabled={!catalog}>Add set</button>
  </header>

  {#if failure}
    <div class="banner banner--error" role="alert">
      <strong>Catalog unavailable.</strong><span>{failure}</span>
    </div>
  {:else if !catalog}
    <section class="workspace-panel loading-panel" aria-live="polite">
      <span class="loading-indicator"></span>
      <div><strong>Loading frequency catalog</strong><p>Resolving sets and definitions.</p></div>
    </section>
  {:else}
    {#if saved}
      <div class="banner banner--success" role="status"><strong>Catalog saved.</strong><span>User-owned records are stored locally.</span></div>
    {/if}

    <div class="catalog-summary" aria-label="Frequency catalog summary">
      <div><strong>{catalog.frequency_definitions.length}</strong><span>Definitions</span></div>
      <div><strong>{catalog.frequency_sets.filter((item) => !item.read_only).length}</strong><span>My sets</span></div>
      <div><strong>{catalog.frequency_sets.filter((item) => item.read_only).length}</strong><span>Preset sets</span></div>
    </div>

    <div class="catalog-layout">
      <aside class="workspace-panel set-browser" aria-labelledby="set-browser-heading">
        <div class="panel-heading">
          <div><p class="section-label">Collections</p><h2 id="set-browser-heading">Frequency sets</h2></div>
        </div>

        <div class="set-section">
          <h3>My sets</h3>
          {#each catalog.frequency_sets.filter((item) => !item.read_only) as frequencySet (frequencySet.id)}
            <button
              class:active={frequencySet.id === selectedSetId}
              class="set-row"
              onclick={() => selectSet(frequencySet.id)}
            >
              <span><strong>{frequencySet.name}</strong><small>User-owned</small></span>
              <b>{frequencySet.members.length}</b>
            </button>
          {:else}
            <p class="empty-copy">No user sets yet.</p>
          {/each}
        </div>

        <div class="set-section">
          <h3>Presets</h3>
          {#each catalog.frequency_sets.filter((item) => item.read_only) as frequencySet (frequencySet.id)}
            <button
              class:active={frequencySet.id === selectedSetId}
              class="set-row"
              onclick={() => selectSet(frequencySet.id)}
            >
              <span><strong>{frequencySet.name}</strong><small>Read only</small></span>
              <b>{frequencySet.members.length}</b>
            </button>
          {/each}
        </div>
      </aside>

      <section class="workspace-panel definition-panel" aria-labelledby="definition-heading">
        {#if selectedSet}
          <div class="panel-heading">
            <div>
              <p class="section-label">{selectedSet.read_only ? "Preset set" : "User set"}</p>
              <h2 id="definition-heading">{selectedSet.name}</h2>
            </div>
            <div class="panel-actions">
              <span class:badge--preset={selectedSet.read_only} class="record-badge">
                {selectedSet.read_only ? "Read only" : "User-owned"}
              </span>
              {#if !selectedSet.read_only}
                <button class="button button--secondary" onclick={removeSet}>Delete set</button>
              {/if}
            </div>
          </div>

          {#if selectedSet.read_only}
            <p class="panel-description">{selectedSet.description}</p>
          {:else}
            <div class="set-editor-fields">
              <label><span>Set name</span><input value={selectedSet.name} onchange={(event) => event.currentTarget.value.trim() && updateSelectedSet({ name: event.currentTarget.value.trim() })} /></label>
              <label class="wide"><span>Description</span><input value={selectedSet.description} oninput={(event) => updateSelectedSet({ description: event.currentTarget.value })} /></label>
            </div>
            <div class="catalog-actions">
              <button class="button button--primary" onclick={addDefinition}>New definition</button>
              <select bind:value={existingDefinitionId} aria-label="Existing frequency definition">
                <option value="">Add an existing definition…</option>
                {#each availableDefinitions as definition (definition.id)}
                  <option value={definition.id}>{definition.name} · {definition.origin}</option>
                {/each}
              </select>
              <button class="button button--secondary" onclick={addExistingDefinition} disabled={!existingDefinitionId}>Add to set</button>
            </div>
          {/if}

          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr><th scope="col">Designation</th><th scope="col">Frequency definition</th><th scope="col">Receive</th><th scope="col">Transmit intent</th><th scope="col">Mode</th><th scope="col">Source</th>{#if !selectedSet.read_only}<th scope="col">Membership</th>{/if}</tr>
              </thead>
              <tbody>
                {#each selectedDefinitions as item (item.definition.id)}
                  <tr class:active-record={item.definition.id === selectedDefinitionId}>
                    <td class="memory-number">
                      {#if selectedSet.read_only}
                        {item.member.channel_designator ?? "—"}
                      {:else}
                        <input class="designator-input" aria-label={`Designation for ${item.definition.name}`} value={item.member.channel_designator ?? ""} placeholder="Optional" oninput={(event) => updateMember(item.definition.id, { channel_designator: event.currentTarget.value || null })} />
                      {/if}
                    </td>
                    <td><button class="definition-link" onclick={() => selectedDefinitionId = item.definition.id}><strong>{item.definition.name}</strong><small>{item.definition.id}</small></button></td>
                    <td class="frequency">{mhz(item.definition.receive_frequency_hz)}</td>
                    <td>{definitionTxSummary(item.definition)}</td>
                    <td>{item.definition.mode}</td>
                    <td><span class:badge--preset={item.definition.read_only} class="record-badge compact">{item.definition.origin}</span></td>
                    {#if !selectedSet.read_only}<td><button class="text-button" onclick={() => removeMembership(item.definition.id)}>Remove</button></td>{/if}
                  </tr>
                {:else}
                  <tr><td colspan={selectedSet.read_only ? 6 : 7} class="empty-table">This set has no frequency definitions yet.</td></tr>
                {/each}
              </tbody>
            </table>
          </div>

          {#if selectedDefinition}
            <div class="definition-editor-heading">
              <div><p class="section-label">Shared definition</p><h3>{selectedDefinition.name}</h3></div>
              <span>{selectedDefinition.read_only ? "Preset definitions cannot be edited." : "Changes apply everywhere this definition is used."}</span>
            </div>

            {#if selectedDefinition.read_only}
              <dl class="definition-facts">
                <div><dt>Receive</dt><dd>{mhz(selectedDefinition.receive_frequency_hz)}</dd></div>
                <div><dt>Transmit intent</dt><dd>{definitionTxSummary(selectedDefinition)}</dd></div>
                <div><dt>Mode</dt><dd>{selectedDefinition.mode}</dd></div>
                <div><dt>Notes</dt><dd>{selectedDefinition.notes || "—"}</dd></div>
              </dl>
            {:else}
              <div class="definition-form">
                <label><span>Name</span><input value={selectedDefinition.name} onchange={(event) => event.currentTarget.value.trim() && updateDefinition({ name: event.currentTarget.value.trim() })} /></label>
                <label><span>Receive MHz</span><input type="number" min="0.000001" step="0.000001" value={selectedDefinition.receive_frequency_hz / 1_000_000} onchange={(event) => updateFrequency("receive_frequency_hz", event.currentTarget.valueAsNumber)} /></label>
                <label><span>Transmit behavior</span><select value={selectedDefinition.transmit_behavior} onchange={(event) => changeTransmitBehavior(event.currentTarget.value)}><option value="same">Same as receive</option><option value="offset">Offset</option><option value="split">Split</option><option value="disabled">Disabled</option></select></label>
                {#if selectedDefinition.transmit_behavior === "offset"}
                  <label><span>Offset MHz</span><input type="number" step="0.000001" value={(selectedDefinition.offset_hz ?? 0) / 1_000_000} onchange={(event) => updateFrequency("offset_hz", event.currentTarget.valueAsNumber)} /></label>
                {:else if selectedDefinition.transmit_behavior === "split"}
                  <label><span>Transmit MHz</span><input type="number" min="0.000001" step="0.000001" value={(selectedDefinition.transmit_frequency_hz ?? selectedDefinition.receive_frequency_hz) / 1_000_000} onchange={(event) => updateFrequency("transmit_frequency_hz", event.currentTarget.valueAsNumber)} /></label>
                {/if}
                <label><span>Mode</span><select value={selectedDefinition.mode} onchange={(event) => updateDefinition({ mode: event.currentTarget.value })}><option>FM</option><option>NFM</option><option>AM</option><option>WFM</option></select></label>
                {#if planSuggestion}
                  <aside class="plan-suggestion wide" aria-label="Frequency plan suggestion">
                    <div>
                      <p>{planSuggestion.plan.source_label} Â· Advisory</p>
                      <strong>{planSuggestion.segment.name}</strong>
                      <span>
                        {#if planSuggestion.segment.suggested_offset_hz !== null}
                          Suggested offset {offsetSummary(planSuggestion.segment.suggested_offset_hz)}.
                        {:else}
                          No repeater offset is suggested for this segment.
                        {/if}
                        {#if planSuggestion.segment.raster_spacing_hz !== null}
                          {planSuggestion.segment.raster_spacing_hz / 1_000} kHz raster:
                          {rasterStatus(selectedDefinition, planSuggestion.segment) ? "on raster" : "off raster"}.
                        {:else}
                          Consult the local coordinator for its frequency raster.
                        {/if}
                      </span>
                      {#if planSuggestion.segment.notes}<small>{planSuggestion.segment.notes}</small>{/if}
                    </div>
                    <div class="plan-suggestion-actions">
                      <a href={planSuggestion.plan.source_url} target="_blank" rel="noreferrer">View source</a>
                      {#if planSuggestion.segment.suggested_offset_hz !== null}
                        <button class="button button--secondary" onclick={applyPlanOffset} disabled={planOffsetApplied(selectedDefinition, planSuggestion.segment)}>
                          {planOffsetApplied(selectedDefinition, planSuggestion.segment) ? "Offset applied" : "Use suggested offset"}
                        </button>
                      {/if}
                    </div>
                  </aside>
                {/if}
                <label><span>Transmit access</span><select value={selectedDefinition.transmit_access.kind} onchange={(event) => changeSignaling("transmit_access", event.currentTarget.value as SignalingKind)}><option value="none">None</option><option value="ctcss">CTCSS</option><option value="dcs">DCS</option></select></label>
                {#if selectedDefinition.transmit_access.kind === "ctcss"}
                  <label><span>Transmit CTCSS Hz</span><input type="number" min="0.1" step="0.1" value={selectedDefinition.transmit_access.ctcss_hz ?? 100} onchange={(event) => updateSignaling("transmit_access", { ctcss_hz: event.currentTarget.valueAsNumber })} /></label>
                {:else if selectedDefinition.transmit_access.kind === "dcs"}
                  <label><span>Transmit DCS code</span><input type="number" min="0" value={selectedDefinition.transmit_access.dcs_code ?? 23} onchange={(event) => updateSignaling("transmit_access", { dcs_code: event.currentTarget.valueAsNumber })} /></label>
                  <label><span>Transmit DCS polarity</span><select value={selectedDefinition.transmit_access.dcs_polarity} onchange={(event) => updateSignaling("transmit_access", { dcs_polarity: event.currentTarget.value as "N" | "R" })}><option>N</option><option>R</option></select></label>
                {/if}
                <label><span>Receive squelch</span><select value={selectedDefinition.receive_squelch.kind} onchange={(event) => changeSignaling("receive_squelch", event.currentTarget.value as SignalingKind)}><option value="none">None</option><option value="ctcss">CTCSS</option><option value="dcs">DCS</option></select></label>
                {#if selectedDefinition.receive_squelch.kind === "ctcss"}
                  <label><span>Receive CTCSS Hz</span><input type="number" min="0.1" step="0.1" value={selectedDefinition.receive_squelch.ctcss_hz ?? 100} onchange={(event) => updateSignaling("receive_squelch", { ctcss_hz: event.currentTarget.valueAsNumber })} /></label>
                {:else if selectedDefinition.receive_squelch.kind === "dcs"}
                  <label><span>Receive DCS code</span><input type="number" min="0" value={selectedDefinition.receive_squelch.dcs_code ?? 23} onchange={(event) => updateSignaling("receive_squelch", { dcs_code: event.currentTarget.valueAsNumber })} /></label>
                  <label><span>Receive DCS polarity</span><select value={selectedDefinition.receive_squelch.dcs_polarity} onchange={(event) => updateSignaling("receive_squelch", { dcs_polarity: event.currentTarget.value as "N" | "R" })}><option>N</option><option>R</option></select></label>
                {/if}
                <label><span>Priority</span><select value={selectedDefinition.priority} onchange={(event) => updateDefinition({ priority: event.currentTarget.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="mandatory">Mandatory</option></select></label>
                <label><span>Tags</span><input value={selectedDefinition.tags.join(", ")} onchange={(event) => updateDefinition({ tags: event.currentTarget.value.split(",").map((item) => item.trim()).filter(Boolean) })} /></label>
                <label class="wide"><span>Notes</span><textarea rows="3" value={selectedDefinition.notes} oninput={(event) => updateDefinition({ notes: event.currentTarget.value })}></textarea></label>
                <div class="wide destructive-row"><button class="button button--secondary" onclick={deleteDefinition}>Delete definition everywhere</button></div>
              </div>
            {/if}
          {/if}
        {:else}
          <div class="empty-workspace"><strong>No frequency sets</strong><p>Add a user-owned set to begin.</p></div>
        {/if}
      </section>
    </div>
  {/if}
</main>
