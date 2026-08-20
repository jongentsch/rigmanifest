<script lang="ts">
  import { onMount } from "svelte";

  import {
    loadCatalog,
    loadDefaultFrequencyPlan,
    saveProfiles,
  } from "$lib/api";
  import {
    definitionTxSummary,
    mhz,
    powerSummary,
    scanSummary,
    signalingSummary,
    tuningStepSummary,
  } from "$lib/format";
  import type {
    FrequencyDefinitionRecord,
    ProfileRecord,
    WorkspaceCatalog,
  } from "$lib/types";

  type ProfileBankPreviewMember = {
    definition: FrequencyDefinitionRecord;
    designation: string;
  };

  type ProfileBankPreviewGroup = {
    id: string;
    name: string;
    assignment: "Bank from set" | "Unassigned additions";
    members: ProfileBankPreviewMember[];
  };

  let catalog = $state<WorkspaceCatalog | null>(null);
  let profiles = $state<ProfileRecord[]>([]);
  let selectedProfileId = $state("");
  let failure = $state("");
  let saved = $state(false);
  let definitionSearch = $state("");
  let draggedSetId = $state("");
  let setDropTargetId = $state("");
  let setDropPosition = $state<"before" | "after">("before");

  let selectedProfile = $derived(
    profiles.find((profile) => profile.id === selectedProfileId) ?? null,
  );
  let filteredDefinitions = $derived(
    (catalog?.frequency_definitions ?? []).filter((definition) => {
      const query = definitionSearch.trim().toLocaleLowerCase();
      return !query || `${definition.name} ${definition.receive_frequency_hz}`.toLocaleLowerCase().includes(query);
    }),
  );
  let bankPreview = $derived(resolveBankPreview(selectedProfile, catalog));
  let selectedFrequencySets = $derived(resolveSelectedSets(selectedProfile, catalog));

  onMount(async () => {
    try {
      const loadedCatalog = await loadCatalog();
      const loadedProfiles = structuredClone(loadedCatalog.profiles);
      catalog = loadedCatalog;
      profiles = loadedProfiles;
      selectedProfileId = profiles[0]?.id ?? "";
    } catch (error) {
      failure = errorMessage(error);
    }
  });

  function addProfile(): void {
    const id = `profile-${Date.now().toString(36)}`;
    const profile: ProfileRecord = {
      id,
      name: "New profile",
      description: "",
      frequency_set_ids: [],
      frequency_definition_ids: [],
      frequency_plan_id: loadDefaultFrequencyPlan(),
    };
    profiles = [...profiles, profile];
    selectedProfileId = id;
    persist();
  }

  function updateProfile(changes: Partial<ProfileRecord>): void {
    profiles = profiles.map((profile) =>
      profile.id === selectedProfileId ? { ...profile, ...changes } : profile,
    );
    persist();
  }

  function toggleSet(setId: string, checked: boolean): void {
    if (!selectedProfile) return;
    updateProfile({
      frequency_set_ids: checked
        ? [...selectedProfile.frequency_set_ids, setId]
        : selectedProfile.frequency_set_ids.filter((id) => id !== setId),
    });
  }

  function resolveSelectedSets(
    profile: ProfileRecord | null,
    workspace: WorkspaceCatalog | null,
  ) {
    if (!profile || !workspace) return [];
    const sets = new Map(
      workspace.frequency_sets.map((frequencySet) => [frequencySet.id, frequencySet]),
    );
    return profile.frequency_set_ids.flatMap((setId) => {
      const frequencySet = sets.get(setId);
      return frequencySet ? [frequencySet] : [];
    });
  }

  function moveProfileSet(setId: string, delta: -1 | 1): void {
    if (!selectedProfile) return;
    const setIds = [...selectedProfile.frequency_set_ids];
    const sourceIndex = setIds.indexOf(setId);
    const targetIndex = sourceIndex + delta;
    if (sourceIndex < 0 || targetIndex < 0 || targetIndex >= setIds.length) return;
    [setIds[sourceIndex], setIds[targetIndex]] = [
      setIds[targetIndex],
      setIds[sourceIndex],
    ];
    updateProfile({ frequency_set_ids: setIds });
  }

  function startSetDrag(event: DragEvent, setId: string): void {
    draggedSetId = setId;
    event.dataTransfer?.setData("text/plain", setId);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
  }

  function dragSetOver(
    event: DragEvent & { currentTarget: HTMLDivElement },
    targetId: string,
  ): void {
    if (!draggedSetId || draggedSetId === targetId) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    const bounds = event.currentTarget.getBoundingClientRect();
    setDropTargetId = targetId;
    setDropPosition = event.clientY >= bounds.top + bounds.height / 2
      ? "after"
      : "before";
  }

  function dropProfileSet(event: DragEvent, targetId: string): void {
    event.preventDefault();
    if (!selectedProfile || !draggedSetId) {
      clearSetDrag();
      return;
    }
    const setIds = [...selectedProfile.frequency_set_ids];
    const sourceIndex = setIds.indexOf(draggedSetId);
    if (sourceIndex < 0 || draggedSetId === targetId) {
      clearSetDrag();
      return;
    }
    const [sourceId] = setIds.splice(sourceIndex, 1);
    const targetIndex = setIds.indexOf(targetId);
    const insertIndex = targetIndex + (setDropPosition === "after" ? 1 : 0);
    setIds.splice(insertIndex, 0, sourceId);
    updateProfile({ frequency_set_ids: setIds });
    clearSetDrag();
  }

  function clearSetDrag(): void {
    draggedSetId = "";
    setDropTargetId = "";
    setDropPosition = "before";
  }

  function setHandleKeydown(event: KeyboardEvent, setId: string): void {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    moveProfileSet(setId, event.key === "ArrowUp" ? -1 : 1);
  }

  function toggleDefinition(definitionId: string, checked: boolean): void {
    if (!selectedProfile) return;
    updateProfile({
      frequency_definition_ids: checked
        ? [...selectedProfile.frequency_definition_ids, definitionId]
        : selectedProfile.frequency_definition_ids.filter((id) => id !== definitionId),
    });
  }

  function resolveBankPreview(
    profile: ProfileRecord | null,
    workspace: WorkspaceCatalog | null,
  ): ProfileBankPreviewGroup[] {
    if (!profile || !workspace) return [];

    const definitions = new Map(
      workspace.frequency_definitions.map((definition) => [definition.id, definition]),
    );
    const sets = new Map(
      workspace.frequency_sets.map((frequencySet) => [frequencySet.id, frequencySet]),
    );
    const assignedDefinitionIds = new Set<string>();
    const groups: ProfileBankPreviewGroup[] = profile.frequency_set_ids.flatMap((setId) => {
      const frequencySet = sets.get(setId);
      if (!frequencySet) return [];
      const members = [...frequencySet.members]
        .sort((left, right) => left.position - right.position)
        .flatMap((member, index) => {
          const definition = definitions.get(member.frequency_definition_id);
          if (!definition) return [];
          assignedDefinitionIds.add(definition.id);
          return [{
            definition,
            designation: member.channel_designator ?? String(index + 1),
          }];
        });
      return [{
        id: frequencySet.id,
        name: frequencySet.name,
        assignment: "Bank from set" as const,
        members,
      }];
    });

    const additions = profile.frequency_definition_ids.flatMap((definitionId) => {
      if (assignedDefinitionIds.has(definitionId)) return [];
      const definition = definitions.get(definitionId);
      return definition ? [{ definition, designation: "—" }] : [];
    });
    if (additions.length > 0) {
      groups.push({
        id: "profile-additions",
        name: "Individual definitions",
        assignment: "Unassigned additions",
        members: additions,
      });
    }
    return groups;
  }

  function deleteProfile(): void {
    if (!selectedProfile) return;
    profiles = profiles.filter((profile) => profile.id !== selectedProfile.id);
    selectedProfileId = profiles[0]?.id ?? "";
    persist();
  }

  function persist(): void {
    saved = false;
    void saveProfiles(profiles)
      .then(() => saved = true)
      .catch((error) => failure = errorMessage(error));
  }

  function errorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    if (error instanceof Error) return error.message;
    return "Profiles could not be loaded.";
  }
</script>

<svelte:head>
  <title>Profiles · RigManifest</title>
  <meta name="description" content="Compose reusable operating profiles from sets and individual frequencies." />
</svelte:head>

<main class="workspace">
  <header class="workspace-header">
    <div>
      <p class="workspace-kicker">Reusable operating intent</p>
      <h1>Profiles</h1>
      <p>Combine sets and individual frequency definitions for places, trips, and operating roles.</p>
    </div>
    <button class="button button--primary" onclick={addProfile} disabled={!catalog}>Add profile</button>
  </header>

  {#if failure}<div class="banner banner--error" role="alert"><strong>Profile error.</strong><span>{failure}</span></div>{/if}
  {#if saved}<div class="banner banner--success" role="status"><strong>Profiles saved.</strong><span>Changes are stored locally.</span></div>{/if}

  {#if catalog}
    <div class="catalog-layout profile-layout">
      <section class="workspace-panel" aria-labelledby="profile-list-heading">
        <div class="panel-heading">
          <div><p class="section-label">Saved loadouts</p><h2 id="profile-list-heading">Profiles</h2></div>
          <span class="schema-label">{profiles.length}</span>
        </div>
        <div class="radio-list-body">
          {#each profiles as profile (profile.id)}
            <button class:active={profile.id === selectedProfileId} class="radio-row" onclick={() => selectedProfileId = profile.id}>
              <span><strong>{profile.name}</strong><small>{profile.frequency_set_ids.length} sets · {profile.frequency_definition_ids.length} individual</small></span>
            </button>
          {:else}
            <p class="empty-copy">Add a profile to create a reusable operating loadout.</p>
          {/each}
        </div>
      </section>

      {#if selectedProfile}
        <section class="workspace-panel" aria-labelledby="profile-editor-heading">
          <div class="panel-heading">
            <div><p class="section-label">Profile configuration</p><h2 id="profile-editor-heading">{selectedProfile.name}</h2></div>
            <button class="button button--secondary" onclick={deleteProfile}>Delete profile</button>
          </div>
          <div class="form-grid profile-basics">
            <label><span>Profile name</span><input value={selectedProfile.name} onchange={(event) => event.currentTarget.value.trim() && updateProfile({ name: event.currentTarget.value.trim() })} /></label>
            <label><span>Advisory band plan</span><select value={selectedProfile.frequency_plan_id ?? ""} onchange={(event) => updateProfile({ frequency_plan_id: event.currentTarget.value || null })}><option value="">Inherit at compile time</option>{#each catalog.frequency_plans as plan}<option value={plan.id}>{plan.name} · {plan.jurisdiction}</option>{/each}</select></label>
            <label class="full"><span>Description</span><textarea rows="2" value={selectedProfile.description} onchange={(event) => updateProfile({ description: event.currentTarget.value })}></textarea></label>
          </div>

          <div class="profile-source-grid">
            <section class="profile-composition" aria-label="Profile composition">
              <div class="profile-composition-group" aria-labelledby="profile-sets-heading">
                <div class="subsection-heading"><div><p class="section-label">Reusable groups</p><h3 id="profile-sets-heading">Frequency sets</h3></div><span>{selectedProfile.frequency_set_ids.length} selected</span></div>
                {#if selectedFrequencySets.length > 0}
                  <div class="selected-set-order" role="list" aria-label="Selected set order">
                    <p>Selected order <span>Drag the handles or use arrow keys.</span></p>
                    {#each selectedFrequencySets as frequencySet, index (frequencySet.id)}
                      <div
                        class="selected-set-order-row"
                        role="listitem"
                        class:dragging-record={frequencySet.id === draggedSetId}
                        class:drop-before={frequencySet.id === setDropTargetId && setDropPosition === "before"}
                        class:drop-after={frequencySet.id === setDropTargetId && setDropPosition === "after"}
                        ondragover={(event) => dragSetOver(event, frequencySet.id)}
                        ondrop={(event) => dropProfileSet(event, frequencySet.id)}
                      >
                        <button
                          class="drag-handle"
                          draggable="true"
                          aria-label={`Reorder ${frequencySet.name}. Use Up and Down arrow keys or drag.`}
                          title="Drag to reorder; arrow keys also work"
                          ondragstart={(event) => startSetDrag(event, frequencySet.id)}
                          ondragend={clearSetDrag}
                          onkeydown={(event) => setHandleKeydown(event, frequencySet.id)}
                        >⋮⋮</button>
                        <span><b>{index + 1}</b><strong>{frequencySet.name}</strong></span>
                      </div>
                    {/each}
                  </div>
                {/if}
                <div class="selection-list profile-selection-list">
                  {#each catalog.frequency_sets as frequencySet (frequencySet.id)}
                    <label class="selection-row"><input type="checkbox" checked={selectedProfile.frequency_set_ids.includes(frequencySet.id)} onchange={(event) => toggleSet(frequencySet.id, event.currentTarget.checked)} /><span><strong>{frequencySet.name}</strong><small>{frequencySet.members.length} definitions · {frequencySet.read_only ? "Preset" : "My set"}</small></span></label>
                  {/each}
                </div>
              </div>

              <div class="profile-composition-group" aria-labelledby="profile-definitions-heading">
                <div class="subsection-heading"><div><p class="section-label">Profile-specific additions</p><h3 id="profile-definitions-heading">Individual definitions</h3></div><span>{selectedProfile.frequency_definition_ids.length} selected</span></div>
                <label class="selection-search"><span>Find a definition</span><input bind:value={definitionSearch} placeholder="Name or frequency" /></label>
                <div class="selection-list profile-selection-list">
                  {#each filteredDefinitions as definition (definition.id)}
                    <label class="selection-row"><input type="checkbox" checked={selectedProfile.frequency_definition_ids.includes(definition.id)} onchange={(event) => toggleDefinition(definition.id, event.currentTarget.checked)} /><span><strong>{definition.name}</strong><small>{(definition.receive_frequency_hz / 1_000_000).toFixed(6)} MHz · {definition.read_only ? "Preset" : "User"}</small></span></label>
                  {/each}
                </div>
              </div>
            </section>

            <section class="profile-bank-preview" aria-labelledby="profile-bank-preview-heading">
              <div class="subsection-heading">
                <div><p class="section-label">Set-based preview</p><h3 id="profile-bank-preview-heading">Prospective banks</h3></div>
              </div>
              <p class="profile-preview-note">This is profile intent, not a compiled radio plan. Radio limits and final bank behavior are applied during compilation.</p>
              <div class="profile-bank-list">
                {#each bankPreview as group (group.id)}
                  <section class="profile-bank-group" aria-label={`${group.name} frequency group`}>
                    <header>
                      <div><span>{group.assignment}</span><h4>{group.name}</h4></div>
                      <b>{group.members.length}</b>
                    </header>
                    <div class="profile-frequency-list" role="table" aria-label={`${group.name} frequencies`} tabindex="0">
                      <div class="profile-frequency-columns" role="row">
                        <span role="columnheader">Slot</span><span role="columnheader">Frequency</span><span role="columnheader">Receive</span><span role="columnheader">Transmit</span><span role="columnheader">TX access</span><span role="columnheader">RX squelch</span><span role="columnheader">Mode</span><span role="columnheader">Step</span><span role="columnheader">Power / scan</span>
                      </div>
                      {#each group.members as member (member.definition.id)}
                        <div class="profile-frequency-row" role="row">
                          <span class="profile-frequency-slot" role="cell">{member.designation}</span>
                          <span role="cell"><strong>{member.definition.name}</strong><small>{member.definition.id}</small></span>
                          <span class="frequency" role="cell">{mhz(member.definition.receive_frequency_hz)}</span>
                          <span role="cell">{definitionTxSummary(member.definition)}</span>
                          <span role="cell">{signalingSummary(member.definition.transmit_access)}</span>
                          <span role="cell">{signalingSummary(member.definition.receive_squelch)}</span>
                          <span role="cell">{member.definition.mode}</span>
                          <span role="cell">{tuningStepSummary(member.definition.tuning_step_hz)}</span>
                          <span role="cell"><strong>{powerSummary(member.definition)}</strong><small>{scanSummary(member.definition.scan_skip)}</small></span>
                        </div>
                      {:else}
                        <p class="empty-copy">This set has no frequency definitions.</p>
                      {/each}
                    </div>
                  </section>
                {:else}
                  <div class="profile-preview-empty"><strong>No frequencies selected</strong><p>Choose sets or individual definitions to preview this profile.</p></div>
                {/each}
              </div>
            </section>
          </div>
        </section>
      {/if}
    </div>
  {:else}
    <section class="workspace-panel loading-panel" aria-live="polite"><span class="loading-indicator"></span><div><strong>Loading profiles</strong><p>Resolving reusable sets and definitions.</p></div></section>
  {/if}
</main>
