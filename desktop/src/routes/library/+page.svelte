<script lang="ts">
  import { onMount } from "svelte";

  import {
    backupWorkspace,
    chooseChirpImportPath,
    chooseWorkspaceBackupPath,
    importChirpCsv,
    loadCatalog,
    loadDefaultFrequencyPlan,
    saveDefaultFrequencyPlan,
    saveWorkspaceUserCatalog,
  } from "$lib/api";
  import { userCatalogFromWorkspace } from "$lib/catalog";
  import {
    definitionTxSummary,
    mhz,
    offsetSummary,
    powerSummary,
    scanSummary,
    signalingSummary,
    tuningStepSummary,
  } from "$lib/format";
  import { advicePlans } from "$lib/plan-preferences";
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
  let viewMode = $state<"all" | "set">("set");
  let selectedSetId = $state("");
  let selectedDefinitionId = $state("");
  let selectedMergeDefinitionIds = $state<string[]>([]);
  let mergeTargetId = $state("");
  let draggedDefinitionId = $state("");
  let definitionDropTargetId = $state("");
  let definitionDropPosition = $state<"before" | "after">("before");
  let selectedPlanId = $state("arrl-us-national");
  let existingDefinitionId = $state("");
  let failure = $state("");
  let saved = $state(false);
  let importing = $state(false);
  let importMessage = $state("");
  let importFailure = $state("");
  let backupMessage = $state("");

  let selectedSet = $derived(
    catalog?.frequency_sets.find((item) => item.id === selectedSetId) ?? null,
  );
  let selectedDefinitions = $derived(resolveDefinitions(selectedSet, catalog));
  let allDefinitions = $derived(
    [...(catalog?.frequency_definitions ?? [])].sort(compareDefinitions),
  );
  let displayedDefinitions = $derived(
    viewMode === "all"
      ? allDefinitions.map((definition) => ({ definition, member: null }))
      : selectedDefinitions,
  );
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
    resolvePlanSuggestion(
      selectedDefinition,
      advicePlans(catalog?.frequency_plans ?? [], selectedPlanId),
    ),
  );
  let mergeDefinitions = $derived(
    selectedMergeDefinitionIds.flatMap((definitionId) => {
      const definition = catalog?.frequency_definitions.find(
        (item) => item.id === definitionId,
      );
      return definition ? [definition] : [];
    }),
  );
  let mergeValidation = $derived(validateMerge(mergeDefinitions, mergeTargetId));

  onMount(async () => {
    try {
      catalog = await loadCatalog();
      selectedPlanId = loadDefaultFrequencyPlan() ?? "arrl-us-national";
      const initialSet =
        catalog.frequency_sets.find((item) => !item.read_only) ??
        catalog.frequency_sets[0] ??
        null;
      selectSet(initialSet?.id ?? "");
    } catch (error) {
      failure = errorMessage(error);
    }
  });

  function selectPlan(nextPlanId: string): void {
    selectedPlanId = nextPlanId;
    void saveDefaultFrequencyPlan(nextPlanId).catch((error) => failure = errorMessage(error));
  }

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
    viewMode = "set";
    selectedSetId = setId;
    const frequencySet = catalog?.frequency_sets.find((item) => item.id === setId);
    selectedDefinitionId =
      [...(frequencySet?.members ?? [])].sort(
        (left, right) => left.position - right.position,
      )[0]?.frequency_definition_id ?? "";
    existingDefinitionId = "";
    clearMergeSelection();
    saved = false;
  }

  function selectAllDefinitions(): void {
    viewMode = "all";
    selectedDefinitionId = allDefinitions[0]?.id ?? "";
    existingDefinitionId = "";
    clearMergeSelection();
    saved = false;
  }

  function selectDefinitionRow(
    node: HTMLTableRowElement,
    definitionId: string,
  ): { destroy: () => void } {
    const handleClick = (event: MouseEvent): void => {
      const target = event.target as HTMLElement;
      if (target.closest("[data-row-action]")) return;
      selectedDefinitionId = definitionId;
    };

    node.addEventListener("click", handleClick);
    return {
      destroy: () => node.removeEventListener("click", handleClick),
    };
  }

  function persist(
    next: WorkspaceCatalog,
    definitionReplacements: Record<string, string> = {},
  ): void {
    catalog = next;
    saved = false;
    void saveWorkspaceUserCatalog(
      userCatalogFromWorkspace(next),
      definitionReplacements,
    )
      .then(() => saved = true)
      .catch((error) => failure = errorMessage(error));
  }

  async function createBackup(): Promise<void> {
    backupMessage = "";
    const destination = await chooseWorkspaceBackupPath();
    if (!destination) return;
    try {
      backupMessage = await backupWorkspace(destination);
    } catch (error) {
      failure = errorMessage(error);
    }
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

  async function importCsv(): Promise<void> {
    if (!catalog || importing) return;
    importing = true;
    importMessage = "";
    importFailure = "";
    try {
      const sourcePath = await chooseChirpImportPath();
      if (!sourcePath) return;
      const imported = await importChirpCsv(sourcePath);
      const next: WorkspaceCatalog = {
        ...catalog,
        frequency_definitions: [
          ...catalog.frequency_definitions,
          ...imported.frequency_definitions,
        ],
        frequency_sets: [...catalog.frequency_sets, imported.frequency_set],
      };
      persist(next);
      selectSet(imported.frequency_set.id);
      saved = true;
      importMessage = `Imported ${imported.definition_count} frequency definitions into ${imported.frequency_set.name}.`;
    } catch (error) {
      importFailure = errorMessage(error);
    } finally {
      importing = false;
    }
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
    if (!catalog) return;
    if (viewMode === "set" && (!selectedSet || selectedSet.read_only)) return;
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
    const member: FrequencySetMemberRecord | null = selectedSet
      ? {
          frequency_definition_id: definition.id,
          position: nextPosition(selectedSet),
          channel_designator: null,
        }
      : null;
    persist({
      ...catalog,
      frequency_definitions: [...catalog.frequency_definitions, definition],
      frequency_sets:
        viewMode === "set" && member
          ? catalog.frequency_sets.map((item) =>
              item.id === selectedSetId
                ? { ...item, members: [...item.members, member] }
                : item,
            )
          : catalog.frequency_sets,
    });
    selectedDefinitionId = definition.id;
  }

  function compareDefinitions(
    left: FrequencyDefinitionRecord,
    right: FrequencyDefinitionRecord,
  ): number {
    return (
      left.receive_frequency_hz - right.receive_frequency_hz ||
      settingsSortKey(left).localeCompare(settingsSortKey(right)) ||
      left.name.localeCompare(right.name) ||
      left.id.localeCompare(right.id)
    );
  }

  function settingsSortKey(definition: FrequencyDefinitionRecord): string {
    return [
      definition.transmit_behavior,
      definition.transmit_frequency_hz ?? "",
      definition.offset_hz ?? "",
      definition.mode,
      signalingSortKey(definition.transmit_access),
      signalingSortKey(definition.receive_squelch),
      definition.tuning_step_hz ?? "",
      definition.power_dbm ?? "",
      definition.power_label ?? "",
      definition.scan_skip ?? "",
      definition.priority,
    ].join("|");
  }

  function signalingSortKey(signaling: SignalingSpec): string {
    return [
      signaling.kind,
      signaling.ctcss_hz ?? "",
      signaling.dcs_code ?? "",
      signaling.dcs_polarity,
    ].join(":");
  }

  function toggleMergeSelection(definitionId: string, checked: boolean): void {
    selectedMergeDefinitionIds = checked
      ? [...selectedMergeDefinitionIds, definitionId]
      : selectedMergeDefinitionIds.filter((item) => item !== definitionId);
    if (!checked && mergeTargetId === definitionId) mergeTargetId = "";
    const selected = allDefinitions.filter((definition) =>
      selectedMergeDefinitionIds.includes(definition.id),
    );
    const preset = selected.find((definition) => definition.read_only);
    if (preset) mergeTargetId = preset.id;
    else if (!selected.some((definition) => definition.id === mergeTargetId)) {
      mergeTargetId = selected[0]?.id ?? "";
    }
  }

  function clearMergeSelection(): void {
    selectedMergeDefinitionIds = [];
    mergeTargetId = "";
  }

  function validateMerge(
    definitions: FrequencyDefinitionRecord[],
    targetId: string,
  ): { valid: boolean; message: string } {
    if (definitions.length < 2) {
      return { valid: false, message: "Select at least two definitions." };
    }
    if (new Set(definitions.map((item) => item.receive_frequency_hz)).size !== 1) {
      return { valid: false, message: "Selected definitions must have the same receive frequency." };
    }
    const presets = definitions.filter((item) => item.read_only);
    if (presets.length > 1) {
      return { valid: false, message: "Preset definitions cannot be merged with each other." };
    }
    if (!definitions.some((item) => item.id === targetId)) {
      return { valid: false, message: "Choose the definition to keep." };
    }
    if (presets.length === 1 && presets[0].id !== targetId) {
      return { valid: false, message: "A preset definition must be the definition kept." };
    }
    return { valid: true, message: "All references will be moved to the definition kept." };
  }

  function mergeSelectedDefinitions(): void {
    if (!catalog || !mergeValidation.valid) return;
    const target = catalog.frequency_definitions.find((item) => item.id === mergeTargetId);
    if (!target) return;
    const sourceIds = new Set(
      selectedMergeDefinitionIds.filter((definitionId) => definitionId !== target.id),
    );
    if (!confirm(
      `Merge ${sourceIds.size} duplicate definition${sourceIds.size === 1 ? "" : "s"} into “${target.name}”? Settings from “${target.name}” will be kept.`,
    )) return;

    const replacements = Object.fromEntries(
      [...sourceIds].map((definitionId) => [definitionId, target.id]),
    );
    const next: WorkspaceCatalog = {
      ...catalog,
      frequency_definitions: catalog.frequency_definitions.filter(
        (definition) => !sourceIds.has(definition.id),
      ),
      frequency_sets: catalog.frequency_sets.map((frequencySet) => ({
        ...frequencySet,
        members: mergeMembers(frequencySet.members, sourceIds, target.id),
      })),
      profiles: catalog.profiles.map((profile) => ({
        ...profile,
        frequency_definition_ids: replaceDefinitionIds(
          profile.frequency_definition_ids,
          sourceIds,
          target.id,
        ),
      })),
    };
    persist(next, replacements);
    selectedDefinitionId = target.id;
    clearMergeSelection();
  }

  function mergeMembers(
    members: FrequencySetMemberRecord[],
    sourceIds: Set<string>,
    targetId: string,
  ): FrequencySetMemberRecord[] {
    let targetSeen = false;
    return [...members]
      .sort((left, right) => left.position - right.position)
      .map((member) => ({
        ...member,
        frequency_definition_id: sourceIds.has(member.frequency_definition_id)
          ? targetId
          : member.frequency_definition_id,
      }))
      .filter((member) => {
        if (member.frequency_definition_id !== targetId) return true;
        if (targetSeen) return false;
        targetSeen = true;
        return true;
      })
      .map((member, position) => ({ ...member, position }));
  }

  function replaceDefinitionIds(
    definitionIds: string[],
    sourceIds: Set<string>,
    targetId: string,
  ): string[] {
    return [...new Set(
      definitionIds.map((definitionId) =>
        sourceIds.has(definitionId) ? targetId : definitionId,
      ),
    )];
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

  function moveDefinition(definitionId: string, delta: -1 | 1): void {
    if (!selectedSet || selectedSet.read_only) return;
    const members = [...selectedSet.members].sort(
      (left, right) => left.position - right.position,
    );
    const sourceIndex = members.findIndex(
      (member) => member.frequency_definition_id === definitionId,
    );
    const targetIndex = sourceIndex + delta;
    if (sourceIndex < 0 || targetIndex < 0 || targetIndex >= members.length) return;
    [members[sourceIndex], members[targetIndex]] = [
      members[targetIndex],
      members[sourceIndex],
    ];
    updateSelectedSet({
      members: members.map((member, position) => ({ ...member, position })),
    });
  }

  function startDefinitionDrag(event: DragEvent, definitionId: string): void {
    if (!selectedSet || selectedSet.read_only) return;
    draggedDefinitionId = definitionId;
    event.dataTransfer?.setData("text/plain", definitionId);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
  }

  function dragDefinitionOver(
    event: DragEvent & { currentTarget: HTMLTableRowElement },
    targetId: string,
  ): void {
    if (!draggedDefinitionId || draggedDefinitionId === targetId) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    const bounds = event.currentTarget.getBoundingClientRect();
    definitionDropTargetId = targetId;
    definitionDropPosition = event.clientY >= bounds.top + bounds.height / 2
      ? "after"
      : "before";
  }

  function dropDefinition(event: DragEvent, targetId: string): void {
    event.preventDefault();
    if (!selectedSet || selectedSet.read_only || !draggedDefinitionId) {
      clearDefinitionDrag();
      return;
    }
    const members = [...selectedSet.members].sort(
      (left, right) => left.position - right.position,
    );
    const sourceIndex = members.findIndex(
      (member) => member.frequency_definition_id === draggedDefinitionId,
    );
    if (sourceIndex < 0 || draggedDefinitionId === targetId) {
      clearDefinitionDrag();
      return;
    }
    const [source] = members.splice(sourceIndex, 1);
    const targetIndex = members.findIndex(
      (member) => member.frequency_definition_id === targetId,
    );
    const insertIndex = targetIndex + (definitionDropPosition === "after" ? 1 : 0);
    members.splice(insertIndex, 0, source);
    updateSelectedSet({
      members: members.map((member, position) => ({ ...member, position })),
    });
    clearDefinitionDrag();
  }

  function clearDefinitionDrag(): void {
    draggedDefinitionId = "";
    definitionDropTargetId = "";
    definitionDropPosition = "before";
  }

  function definitionHandleKeydown(event: KeyboardEvent, definitionId: string): void {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    moveDefinition(definitionId, event.key === "ArrowUp" ? -1 : 1);
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
    if (kind === "ctcss") signaling.ctcss_hz = defaultCtcssTone();
    if (kind === "dcs") signaling.dcs_code = 23;
    updateDefinition({ [direction]: signaling });
  }

  function defaultCtcssTone(): number {
    const tones = catalog?.ctcss_tones_hz ?? [];
    return tones.includes(100) ? 100 : tones[0] ?? 100;
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
        `Delete “${selectedDefinition.name}” everywhere? It will be removed from all user sets and profiles. This cannot be undone.`,
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
    selectedDefinitionId = viewMode === "all"
      ? [...next.frequency_definitions].sort(compareDefinitions)[0]?.id ?? ""
      : next.frequency_sets
          .find((item) => item.id === selectedSetId)
          ?.members[0]?.frequency_definition_id ?? "";
    selectedMergeDefinitionIds = selectedMergeDefinitionIds.filter(
      (item) => item !== definitionId,
    );
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
    <div class="header-actions">
      <button class="button button--secondary" onclick={createBackup} disabled={!catalog}>Back up data</button>
      <button class="button button--secondary" onclick={importCsv} disabled={!catalog || importing}>{importing ? "Importingâ€¦" : "Import CHIRP CSV"}</button>
    </div>
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
    {#if importFailure}
      <div class="banner banner--error" role="alert"><strong>Import failed.</strong><span>{importFailure}</span></div>
    {:else if importMessage}
      <div class="banner banner--success" role="status"><strong>CHIRP CSV imported.</strong><span>{importMessage}</span></div>
    {/if}
    {#if backupMessage}
      <div class="banner banner--success" role="status"><strong>Data backed up.</strong><span>{backupMessage}</span></div>
    {/if}
    {#if saved && !importMessage}
      <div class="banner banner--success" role="status"><strong>Catalog saved.</strong><span>User-owned records are stored locally.</span></div>
    {/if}

    <div class="catalog-layout">
      <aside class="workspace-panel set-browser" aria-labelledby="set-browser-heading">
        <div class="all-frequency-section">
          <button
            class:active={viewMode === "all"}
            class="set-row all-frequency-row"
            onclick={selectAllDefinitions}
          >
            <span><strong>All frequencies</strong><small>View, edit, and merge definitions</small></span>
            <b>{catalog.frequency_definitions.length}</b>
          </button>
        </div>
        <div class="panel-heading">
          <div><p class="section-label">Collections</p><h2 id="set-browser-heading">Frequency sets</h2></div>
          <button class="button button--primary" onclick={addSet}>Add set</button>
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
        {#if viewMode === "all" || selectedSet}
          {#if viewMode === "all"}
            <div class="panel-heading">
              <div>
                <p class="section-label">Shared catalog</p>
                <h2 id="definition-heading">All frequencies</h2>
              </div>
              <div class="panel-actions">
                <span class="record-badge">{allDefinitions.length} definitions</span>
                <button class="button button--primary" onclick={addDefinition}>New definition</button>
              </div>
            </div>
            <p class="panel-description">Every definition in the catalog, sorted by receive frequency and then settings. Presets remain read-only.</p>
            <div class="merge-actions" aria-label="Merge frequency definitions">
              <span>{selectedMergeDefinitionIds.length} selected</span>
              <label>
                <span>Keep</span>
                <select aria-label="Definition to keep" bind:value={mergeTargetId} disabled={selectedMergeDefinitionIds.length < 2}>
                  <option value="">Choose a definition…</option>
                  {#each mergeDefinitions as definition (definition.id)}
                    <option value={definition.id} disabled={mergeDefinitions.some((item) => item.read_only) && !definition.read_only}>
                      {definition.name} · {definition.read_only ? "Preset" : "User"}
                    </option>
                  {/each}
                </select>
              </label>
              <button class="button button--secondary" onclick={mergeSelectedDefinitions} disabled={!mergeValidation.valid}>Merge selected</button>
              <small class:merge-error={selectedMergeDefinitionIds.length >= 2 && !mergeValidation.valid}>{mergeValidation.message}</small>
            </div>
          {:else if selectedSet}
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
              {#if selectedSet.source_label}
                <p class="preset-source">
                  <span>{selectedSet.jurisdiction ?? "Published preset"} · reviewed {selectedSet.reviewed_at ?? "date unavailable"}</span>
                  {#if selectedSet.source_url}
                    <a href={selectedSet.source_url} target="_blank" rel="noreferrer">{selectedSet.source_label}</a>
                  {:else}
                    <strong>{selectedSet.source_label}</strong>
                  {/if}
                </p>
              {/if}
            {:else}
              <div class="set-editor-fields">
                <label><span>Set name</span><input value={selectedSet.name} onchange={(event) => event.currentTarget.value.trim() && updateSelectedSet({ name: event.currentTarget.value.trim() })} /></label>
                <label class="wide"><span>Description</span><input value={selectedSet.description} onchange={(event) => updateSelectedSet({ description: event.currentTarget.value })} /></label>
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
          {/if}

          <div class="table-wrap" role="region" aria-label={viewMode === "all" ? "All frequency definitions" : `${selectedSet?.name ?? "Selected set"} frequency table`} tabindex="0">
            <table class="data-table">
              <thead>
                <tr>{#if viewMode === "all"}<th scope="col" class="selection-cell"><span class="visually-hidden">Merge selection</span></th>{:else}<th scope="col">Designation</th>{/if}<th scope="col">Frequency definition</th><th scope="col">Receive</th><th scope="col">Transmit</th><th scope="col">TX access</th><th scope="col">RX squelch</th><th scope="col">Mode</th><th scope="col">Step</th><th scope="col">Power / scan</th><th scope="col">Source</th>{#if viewMode === "set" && selectedSet && !selectedSet.read_only}<th scope="col">Membership</th>{/if}</tr>
              </thead>
              <tbody>
                {#each displayedDefinitions as item (item.definition.id)}
                  <tr
                    class:active-record={item.definition.id === selectedDefinitionId}
                    class:dragging-record={item.definition.id === draggedDefinitionId}
                    class:drop-before={item.definition.id === definitionDropTargetId && definitionDropPosition === "before"}
                    class:drop-after={item.definition.id === definitionDropTargetId && definitionDropPosition === "after"}
                    class="selectable-record"
                    use:selectDefinitionRow={item.definition.id}
                    ondragover={(event) => viewMode === "set" && dragDefinitionOver(event, item.definition.id)}
                    ondrop={(event) => viewMode === "set" && dropDefinition(event, item.definition.id)}
                  >
                    {#if viewMode === "all"}
                      <td class="selection-cell"><input type="checkbox" data-row-action aria-label={`Select ${item.definition.name} for merge`} checked={selectedMergeDefinitionIds.includes(item.definition.id)} onchange={(event) => toggleMergeSelection(item.definition.id, event.currentTarget.checked)} /></td>
                    {:else}
                      <td class="memory-number">
                        {#if selectedSet?.read_only}
                          {item.member?.channel_designator ?? "—"}
                        {:else}
                          <div class="membership-order-control">
                            <button
                              class="drag-handle"
                              data-row-action
                              draggable="true"
                              aria-label={`Reorder ${item.definition.name}. Use Up and Down arrow keys or drag.`}
                              title="Drag to reorder; arrow keys also work"
                              ondragstart={(event) => startDefinitionDrag(event, item.definition.id)}
                              ondragend={clearDefinitionDrag}
                              onkeydown={(event) => definitionHandleKeydown(event, item.definition.id)}
                            >⋮⋮</button>
                            <input class="designator-input" aria-label={`Designation for ${item.definition.name}`} value={item.member?.channel_designator ?? ""} placeholder="Optional" oninput={(event) => updateMember(item.definition.id, { channel_designator: event.currentTarget.value || null })} />
                          </div>
                        {/if}
                      </td>
                    {/if}
                    <td><button class="definition-link" onclick={() => selectedDefinitionId = item.definition.id}><strong>{item.definition.name}</strong><small>{item.definition.id}</small></button></td>
                    <td class="frequency">{mhz(item.definition.receive_frequency_hz)}</td>
                    <td>{definitionTxSummary(item.definition)}</td>
                    <td>{signalingSummary(item.definition.transmit_access)}</td>
                    <td>{signalingSummary(item.definition.receive_squelch)}</td>
                    <td>{item.definition.mode}</td>
                    <td>{tuningStepSummary(item.definition.tuning_step_hz)}</td>
                    <td><strong>{powerSummary(item.definition)}</strong><small>{scanSummary(item.definition.scan_skip)}</small></td>
                    <td><span class:badge--preset={item.definition.read_only} class="record-badge compact">{item.definition.origin}</span></td>
                    {#if viewMode === "set" && selectedSet && !selectedSet.read_only}<td><button class="text-button" data-row-action onclick={() => removeMembership(item.definition.id)}>Remove</button></td>{/if}
                  </tr>
                {:else}
                  <tr><td colspan={viewMode === "all" ? 10 : selectedSet?.read_only ? 10 : 11} class="empty-table">{viewMode === "all" ? "The catalog has no frequency definitions yet." : "This set has no frequency definitions yet."}</td></tr>
                {/each}
              </tbody>
            </table>
          </div>

          {#if selectedDefinition}
            <div class="definition-editor-heading">
              <div>
                <p class="section-label">Shared definition</p>
                <h3>{selectedDefinition.name}</h3>
                <span class="definition-usage">{selectedDefinition.read_only ? "Preset definitions cannot be edited." : "Changes apply everywhere this definition is used."}</span>
              </div>
              <label class="definition-advisory">
                <span>Advisory plan</span>
                <select aria-label="Advisory context for definitions" value={selectedPlanId} onchange={(event) => selectPlan(event.currentTarget.value)}>
                  {#each catalog.frequency_plans as frequencyPlan}<option value={frequencyPlan.id}>{frequencyPlan.name} · {frequencyPlan.jurisdiction}</option>{/each}
                </select>
              </label>
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
                <label><span>Mode</span><select value={selectedDefinition.mode} onchange={(event) => updateDefinition({ mode: event.currentTarget.value })}><option>FM</option><option>NFM</option><option>AM</option><option>WFM</option><option>USB</option><option>CW</option></select></label>
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
                  <label><span>Transmit CTCSS Hz</span><select value={selectedDefinition.transmit_access.ctcss_hz ?? defaultCtcssTone()} onchange={(event) => updateSignaling("transmit_access", { ctcss_hz: Number(event.currentTarget.value) })}>{#each catalog?.ctcss_tones_hz ?? [] as tone}<option value={tone}>{tone.toFixed(1)}</option>{/each}</select></label>
                {:else if selectedDefinition.transmit_access.kind === "dcs"}
                  <label><span>Transmit DCS code</span><input type="number" min="0" value={selectedDefinition.transmit_access.dcs_code ?? 23} onchange={(event) => updateSignaling("transmit_access", { dcs_code: event.currentTarget.valueAsNumber })} /></label>
                  <label><span>Transmit DCS polarity</span><select value={selectedDefinition.transmit_access.dcs_polarity} onchange={(event) => updateSignaling("transmit_access", { dcs_polarity: event.currentTarget.value as "N" | "R" })}><option>N</option><option>R</option></select></label>
                {/if}
                <label><span>Receive squelch</span><select value={selectedDefinition.receive_squelch.kind} onchange={(event) => changeSignaling("receive_squelch", event.currentTarget.value as SignalingKind)}><option value="none">None</option><option value="ctcss">CTCSS</option><option value="dcs">DCS</option></select></label>
                {#if selectedDefinition.receive_squelch.kind === "ctcss"}
                  <label><span>Receive CTCSS Hz</span><select value={selectedDefinition.receive_squelch.ctcss_hz ?? defaultCtcssTone()} onchange={(event) => updateSignaling("receive_squelch", { ctcss_hz: Number(event.currentTarget.value) })}>{#each catalog?.ctcss_tones_hz ?? [] as tone}<option value={tone}>{tone.toFixed(1)}</option>{/each}</select></label>
                {:else if selectedDefinition.receive_squelch.kind === "dcs"}
                  <label><span>Receive DCS code</span><input type="number" min="0" value={selectedDefinition.receive_squelch.dcs_code ?? 23} onchange={(event) => updateSignaling("receive_squelch", { dcs_code: event.currentTarget.valueAsNumber })} /></label>
                  <label><span>Receive DCS polarity</span><select value={selectedDefinition.receive_squelch.dcs_polarity} onchange={(event) => updateSignaling("receive_squelch", { dcs_polarity: event.currentTarget.value as "N" | "R" })}><option>N</option><option>R</option></select></label>
                {/if}
                <label><span>Priority</span><select value={selectedDefinition.priority} onchange={(event) => updateDefinition({ priority: event.currentTarget.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="mandatory">Mandatory</option></select></label>
                <label><span>Tags</span><input value={selectedDefinition.tags.join(", ")} onchange={(event) => updateDefinition({ tags: event.currentTarget.value.split(",").map((item) => item.trim()).filter(Boolean) })} /></label>
                <label class="wide"><span>Notes</span><textarea rows="3" value={selectedDefinition.notes} onchange={(event) => updateDefinition({ notes: event.currentTarget.value })}></textarea></label>
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
