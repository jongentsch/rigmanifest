<script lang="ts">
  import { onMount } from "svelte";

  import {
    loadCatalog,
    loadDefaultFrequencyPlan,
    saveProfiles,
  } from "$lib/api";
  import type { ProfileRecord, WorkspaceCatalog } from "$lib/types";

  let catalog = $state<WorkspaceCatalog | null>(null);
  let profiles = $state<ProfileRecord[]>([]);
  let selectedProfileId = $state("");
  let failure = $state("");
  let saved = $state(false);
  let definitionSearch = $state("");

  let selectedProfile = $derived(
    profiles.find((profile) => profile.id === selectedProfileId) ?? null,
  );
  let filteredDefinitions = $derived(
    (catalog?.frequency_definitions ?? []).filter((definition) => {
      const query = definitionSearch.trim().toLocaleLowerCase();
      return !query || `${definition.name} ${definition.receive_frequency_hz}`.toLocaleLowerCase().includes(query);
    }),
  );

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

  function toggleDefinition(definitionId: string, checked: boolean): void {
    if (!selectedProfile) return;
    updateProfile({
      frequency_definition_ids: checked
        ? [...selectedProfile.frequency_definition_ids, definitionId]
        : selectedProfile.frequency_definition_ids.filter((id) => id !== definitionId),
    });
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
            <section aria-labelledby="profile-sets-heading">
              <div class="subsection-heading"><div><p class="section-label">Reusable groups</p><h3 id="profile-sets-heading">Frequency sets</h3></div><span>{selectedProfile.frequency_set_ids.length} selected</span></div>
              <div class="selection-list">
                {#each catalog.frequency_sets as frequencySet (frequencySet.id)}
                  <label class="selection-row"><input type="checkbox" checked={selectedProfile.frequency_set_ids.includes(frequencySet.id)} onchange={(event) => toggleSet(frequencySet.id, event.currentTarget.checked)} /><span><strong>{frequencySet.name}</strong><small>{frequencySet.members.length} definitions · {frequencySet.read_only ? "Preset" : "My set"}</small></span></label>
                {/each}
              </div>
            </section>

            <section aria-labelledby="profile-definitions-heading">
              <div class="subsection-heading"><div><p class="section-label">Profile-specific additions</p><h3 id="profile-definitions-heading">Individual definitions</h3></div><span>{selectedProfile.frequency_definition_ids.length} selected</span></div>
              <label class="selection-search"><span>Find a definition</span><input bind:value={definitionSearch} placeholder="Name or frequency" /></label>
              <div class="selection-list">
                {#each filteredDefinitions as definition (definition.id)}
                  <label class="selection-row"><input type="checkbox" checked={selectedProfile.frequency_definition_ids.includes(definition.id)} onchange={(event) => toggleDefinition(definition.id, event.currentTarget.checked)} /><span><strong>{definition.name}</strong><small>{(definition.receive_frequency_hz / 1_000_000).toFixed(6)} MHz · {definition.read_only ? "Preset" : "User"}</small></span></label>
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
