<script lang="ts">
  import { onMount } from "svelte";

  import {
    chooseChirpImagePath,
    importChirpImage,
    loadCatalog,
    loadProfiles,
    loadRadioInventory,
    listRadioImages,
    saveProfiles,
    saveRadioInventory,
    saveWorkspaceUserCatalog,
  } from "$lib/api";
  import type {
    RadioInstance,
    RadioImageVersion,
    WorkspaceCatalog,
  } from "$lib/types";

  let catalog = $state<WorkspaceCatalog | null>(null);
  let radios = $state<RadioInstance[]>([]);
  let selectedRadioId = $state("");
  let failure = $state("");
  let saved = $state(false);
  let importing = $state(false);
  let imageVersions = $state<RadioImageVersion[]>([]);
  let versionsLoading = $state(false);

  let selectedRadio = $derived(radios.find((item) => item.id === selectedRadioId) ?? null);

  onMount(async () => {
    try {
      catalog = await loadCatalog();
      radios = loadRadioInventory();
      selectedRadioId = radios[0]?.id ?? "";
      if (selectedRadioId) await refreshImageVersions(selectedRadioId);
    } catch (error) {
      failure = errorMessage(error);
    }
  });

  function updateRadio(changes: Partial<RadioInstance>): void {
    radios = radios.map((item) =>
      item.id === selectedRadioId ? { ...item, ...changes } : item,
    );
    saved = false;
  }

  async function selectRadio(radioId: string): Promise<void> {
    selectedRadioId = radioId;
    await refreshImageVersions(radioId);
  }

  async function refreshImageVersions(radioId: string): Promise<void> {
    versionsLoading = true;
    try {
      const versions = await listRadioImages(radioId);
      if (selectedRadioId === radioId) imageVersions = versions;
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      versionsLoading = false;
    }
  }

  async function addRadioFromImage(): Promise<void> {
    if (!catalog) return;
    const sourcePath = await chooseChirpImagePath();
    if (!sourcePath) return;
    importing = true;
    failure = "";
    saved = false;
    const radioId = crypto.randomUUID();
    try {
      const imported = await importChirpImage(radioId, sourcePath);
      const radio: RadioInstance = {
        id: radioId,
        name: `My ${imported.model}`,
        radioModelId: `chirp:${imported.driver_reference}`,
        driverReference: imported.driver_reference,
        manufacturer: imported.manufacturer,
        model: imported.model,
        imageFilename: imported.source_filename,
        memoryCapacity: imported.memory_capacity,
        maxLabelLength: imported.max_label_length,
        bankCount: imported.bank_count,
        settingCount: imported.setting_count,
        memoryStart: imported.memory_start,
        mapSetsToBanks: imported.bank_count > 0,
        notes: "",
      };
      radios = [...radios, radio];
      selectedRadioId = radio.id;
      imageVersions = [imported.image_version];

      const definitions = mergeById(
        catalog.frequency_definitions,
        imported.frequency_definitions,
      );
      const sets = mergeById(catalog.frequency_sets, imported.frequency_sets);
      catalog = { ...catalog, frequency_definitions: definitions, frequency_sets: sets };
      await saveRadioInventory(radios);
      await saveWorkspaceUserCatalog({
        frequencyDefinitions: definitions.filter((item) => !item.read_only),
        frequencySets: sets.filter((item) => !item.read_only),
      });
      const profiles = mergeById(loadProfiles(), [imported.profile]);
      await saveProfiles(profiles);
      catalog = { ...catalog, profiles };
      saved = true;
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      importing = false;
    }
  }

  function removeRadio(): void {
    if (!selectedRadio) return;
    const remaining = radios.filter((item) => item.id !== selectedRadio.id);
    radios = remaining;
    selectedRadioId = remaining[0]?.id ?? "";
    imageVersions = [];
    if (selectedRadioId) void refreshImageVersions(selectedRadioId);
    void saveRadioInventory(radios).catch((error) => failure = errorMessage(error));
  }

  async function persist(): Promise<void> {
    try {
      await saveRadioInventory(radios);
      saved = true;
    } catch (error) {
      failure = errorMessage(error);
    }
  }

  function errorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    if (error instanceof Error) return error.message;
    return "The radio inventory could not be loaded.";
  }

  function mergeById<T extends { id: string }>(existing: T[], additions: T[]): T[] {
    const additionIds = new Set(additions.map((item) => item.id));
    return [...existing.filter((item) => !additionIds.has(item.id)), ...additions];
  }

  function versionDate(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
  }

  function fileSize(value: number): string {
    if (value < 1024) return `${value} B`;
    return `${(value / 1024).toFixed(1)} KB`;
  }
</script>

<svelte:head><title>My radios · RigManifest</title></svelte:head>

<main class="workspace">
  <header class="workspace-header">
    <div>
      <p class="workspace-kicker">Radio inventory</p>
      <h1>My radios</h1>
      <p>Add a current CHIRP image. RigManifest detects the model and imports its memories and banks.</p>
    </div>
    <button class="button button--primary" onclick={addRadioFromImage} disabled={!catalog || importing}>
      {importing ? "Reading image…" : "Add radio from IMG"}
    </button>
  </header>

  {#if failure}
    <div class="banner banner--error" role="alert"><strong>Radio unavailable.</strong><span>{failure}</span></div>
  {/if}
  {#if saved}
    <div class="banner banner--success" role="status"><strong>Radio saved.</strong><span>The image, memories, and bank sets are stored in this workspace.</span></div>
  {/if}

  {#if !catalog}
    <section class="workspace-panel loading-panel" aria-live="polite">
      <span class="loading-indicator"></span><div><strong>Loading radios</strong><p>Reading the local workspace.</p></div>
    </section>
  {:else if radios.length === 0}
    <section class="workspace-panel compile-empty">
      <p class="section-label">No radios yet</p>
      <h2>Start with a fresh CHIRP clone</h2>
      <p>Download the radio in CHIRP, save its image, then add that IMG here. The original image is preserved in the workspace.</p>
      <button class="button button--primary" onclick={addRadioFromImage} disabled={importing}>Add radio from IMG</button>
    </section>
  {:else if selectedRadio}
    <div class="radio-layout">
      <aside class="workspace-panel radio-list" aria-label="Saved radios">
        <div class="panel-heading"><div><p class="section-label">Inventory</p><h2>{radios.length} radios</h2></div></div>
        <div class="radio-list-body">
          {#each radios as radio (radio.id)}
            <button class:active={radio.id === selectedRadioId} class="radio-row" onclick={() => void selectRadio(radio.id)}>
              <span><strong>{radio.name}</strong><small>{radio.manufacturer ?? "Image required"} {radio.model ?? radio.radioModelId}</small></span>
            </button>
          {/each}
        </div>
      </aside>

      <section class="workspace-panel radio-editor" aria-labelledby="radio-editor-heading">
        <div class="panel-heading">
          <div><p class="section-label">Image-backed radio</p><h2 id="radio-editor-heading">{selectedRadio.name}</h2></div>
          <div class="panel-actions">
            <button class="button button--secondary" onclick={removeRadio}>Remove</button>
            <button class="button button--primary" onclick={persist}>Save radio</button>
          </div>
        </div>

        <div class="form-grid">
          <label><span>Radio name</span><input value={selectedRadio.name} oninput={(event) => updateRadio({ name: event.currentTarget.value })} /></label>
          <label><span>Detected model</span><input value={`${selectedRadio.manufacturer ?? "Unknown"} ${selectedRadio.model ?? ""}`} disabled /></label>
          <label class="full"><span>Source image</span><input value={selectedRadio.imageFilename ?? "No image imported"} disabled /></label>
          <label><span>First programmable memory</span><input type="number" min="0" value={selectedRadio.memoryStart} oninput={(event) => updateRadio({ memoryStart: event.currentTarget.valueAsNumber })} /></label>
          <label class="check-field"><input type="checkbox" checked={selectedRadio.mapSetsToBanks} disabled={(selectedRadio.bankCount ?? 0) === 0} onchange={(event) => updateRadio({ mapSetsToBanks: event.currentTarget.checked })} /><span>Map selected sets to radio banks</span></label>
          <label class="full"><span>Notes</span><textarea rows="4" value={selectedRadio.notes} oninput={(event) => updateRadio({ notes: event.currentTarget.value })}></textarea></label>
        </div>

        <div class="model-facts">
          <div><span>Memory locations</span><strong>{selectedRadio.memoryCapacity ?? "—"}</strong></div>
          <div><span>Label length</span><strong>{selectedRadio.maxLabelLength ?? "—"}</strong></div>
          <div><span>Banks</span><strong>{selectedRadio.bankCount ?? "—"}</strong></div>
          <div><span>Preserved settings</span><strong>{selectedRadio.settingCount ?? "—"}</strong></div>
        </div>

        <div class="factory-section">
          <div class="inspector-section-heading"><h3>Imported bank sets</h3><span>{catalog.frequency_sets.filter((item) => item.id.startsWith(`user-radio-${selectedRadio.id}-`)).length}</span></div>
          <p class="empty-copy">Banks are ordinary frequency sets. Profiles can group any combination of them; radios without bank support receive the same memories as a flat list.</p>
        </div>


        <div class="image-history">
          <div class="inspector-section-heading"><h3>Radio image versions</h3><span>{imageVersions.length}</span></div>
          {#if versionsLoading}
            <p class="empty-copy" aria-live="polite">Reading stored images…</p>
          {:else if imageVersions.length === 0}
            <p class="empty-copy">No managed image files were found for this radio.</p>
          {:else}
            <div class="image-version-list">
              {#each imageVersions as version (version.id)}
                <article class="image-version">
                  <div class="image-version-heading">
                    <span class:source={version.kind === "source"} class="image-kind">{version.kind === "source" ? "Imported source" : "Compiled"}</span>
                    <strong>{version.filename}</strong>
                  </div>
                  <div class="image-version-meta">
                    <span>{versionDate(version.created_at)}</span>
                    <span>{fileSize(version.byte_size)}</span>
                    <span title={version.sha256}>SHA-256 {version.sha256.slice(0, 10)}…</span>
                  </div>
                  <code>{version.path}</code>
                </article>
              {/each}
            </div>
          {/if}
        </div>
      </section>
    </div>
  {/if}
</main>
