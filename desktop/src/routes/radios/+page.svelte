<script lang="ts">
  import { onMount } from "svelte";

  import { loadCatalog, loadRadioInventory, saveRadioInventory } from "$lib/api";
  import { createRadioInstance } from "$lib/radios";
  import type { RadioInstance, RadioModelRecord, WorkspaceCatalog } from "$lib/types";

  let catalog = $state<WorkspaceCatalog | null>(null);
  let radios = $state<RadioInstance[]>([]);
  let selectedRadioId = $state("");
  let failure = $state("");
  let saved = $state(false);
  let modelQuery = $state("");

  let selectedRadio = $derived(radios.find((item) => item.id === selectedRadioId) ?? null);
  let selectedModel = $derived(
    catalog?.radio_models.find((item) => item.id === selectedRadio?.radioModelId) ?? null,
  );
  let modelGroups = $derived(groupModels(catalog?.radio_models ?? [], modelQuery));

  onMount(async () => {
    try {
      catalog = await loadCatalog();
      radios = loadRadioInventory();
      selectedRadioId = radios[0]?.id ?? "";
      const initialModel =
        catalog.radio_models.find((item) => item.id === radios[0]?.radioModelId) ??
        catalog.radio_models[0];
      modelQuery = initialModel ? modelLabel(initialModel) : "";
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

  function addRadio(): void {
    const model = catalog?.radio_models[0];
    if (!model) return;
    const radio = createRadioInstance(model.id, model.memory_start);
    radios = [...radios, radio];
    selectedRadioId = radio.id;
    modelQuery = modelLabel(model);
    saved = false;
  }

  function removeRadio(): void {
    if (radios.length <= 1) return;
    const remaining = radios.filter((item) => item.id !== selectedRadioId);
    radios = remaining;
    selectedRadioId = remaining[0]?.id ?? "";
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

  function chooseModel(model: RadioModelRecord): void {
    updateRadio({
      radioModelId: model.id,
      memoryStart: model.memory_start,
    });
    modelQuery = modelLabel(model);
  }

  function selectRadio(radio: RadioInstance): void {
    selectedRadioId = radio.id;
    const model = catalog?.radio_models.find(
      (item) => item.id === radio.radioModelId,
    );
    modelQuery = model ? modelLabel(model) : "";
    saved = false;
  }

  function errorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    if (error instanceof Error) return error.message;
    return "The radio inventory could not be loaded.";
  }

  function modelLabel(model: RadioModelRecord): string {
    return `${model.manufacturer} ${model.model}`;
  }

  function groupModels(
    models: RadioModelRecord[],
    query: string,
  ): Array<{ manufacturer: string; models: RadioModelRecord[] }> {
    const needle = query.trim().toLocaleLowerCase();
    const filtered = models.filter((model) =>
      `${model.manufacturer} ${model.model}`.toLocaleLowerCase().includes(needle),
    );
    const manufacturers = new Map<string, RadioModelRecord[]>();
    for (const model of filtered) {
      const group = manufacturers.get(model.manufacturer) ?? [];
      group.push(model);
      manufacturers.set(model.manufacturer, group);
    }
    return [...manufacturers.entries()].map(([manufacturer, groupedModels]) => ({
      manufacturer,
      models: groupedModels,
    }));
  }
</script>

<svelte:head><title>My radios · RigManifest</title></svelte:head>

<main class="workspace">
  <header class="workspace-header">
    <div>
      <p class="workspace-kicker">Radio inventory</p>
      <h1>My radios</h1>
      <p>Name each radio, choose its model, and configure compilation behavior.</p>
    </div>
    <button class="button button--primary" onclick={addRadio} disabled={!catalog}>Add radio</button>
  </header>

  {#if failure}
    <div class="banner banner--error" role="alert"><strong>Inventory unavailable.</strong><span>{failure}</span></div>
  {:else if !catalog || !selectedRadio}
    <section class="workspace-panel loading-panel" aria-live="polite">
      <span class="loading-indicator"></span><div><strong>Loading radios</strong><p>Reading local inventory.</p></div>
    </section>
  {:else}
    {#if saved}
      <div class="banner banner--success" role="status"><strong>Radio saved.</strong><span>Local inventory updated.</span></div>
    {/if}

    <div class="radio-layout">
      <aside class="workspace-panel radio-list" aria-label="Saved radios">
        <div class="panel-heading"><div><p class="section-label">Inventory</p><h2>{radios.length} radios</h2></div></div>
        <div class="radio-list-body">
          {#each radios as radio (radio.id)}
            <button
              class:active={radio.id === selectedRadioId}
              class="radio-row"
              onclick={() => selectRadio(radio)}
            >
              <span><strong>{radio.name}</strong><small>{catalog.radio_models.find((item) => item.id === radio.radioModelId)?.model ?? radio.radioModelId}</small></span>
            </button>
          {/each}
        </div>
      </aside>

      <section class="workspace-panel radio-editor" aria-labelledby="radio-editor-heading">
        <div class="panel-heading">
          <div><p class="section-label">Radio configuration</p><h2 id="radio-editor-heading">{selectedRadio.name}</h2></div>
          <div class="panel-actions">
            <button class="button button--secondary" onclick={removeRadio} disabled={radios.length <= 1}>Remove</button>
            <button class="button button--primary" onclick={persist}>Save radio</button>
          </div>
        </div>

        <div class="form-grid">
          <label><span>Radio name</span><input value={selectedRadio.name} oninput={(event) => updateRadio({ name: event.currentTarget.value })} /></label>
          <div class="model-picker full">
            <label for="model-search"><span>Find manufacturer or model</span></label>
            <input id="model-search" type="search" bind:value={modelQuery} autocomplete="off" placeholder="Search Yaesu, Quansheng, Retevisâ€¦" />
            <div class="model-picker-results" aria-label="Radio model results" aria-live="polite">
              {#each modelGroups as group (group.manufacturer)}
                <section>
                  <h3>{group.manufacturer}</h3>
                  {#each group.models as model (model.id)}
                    <button
                      type="button"
                      class:selected={model.id === selectedRadio.radioModelId}
                      aria-pressed={model.id === selectedRadio.radioModelId}
                      onclick={() => chooseModel(model)}
                    >
                      <span><strong>{model.model}</strong><small>{model.chirp_driver_reference ?? "No CHIRP driver"}</small></span>
                      {#if model.id === selectedRadio.radioModelId}<b>Selected</b>{/if}
                    </button>
                  {/each}
                </section>
              {:else}
                <p>No radio models match â€œ{modelQuery}â€.</p>
              {/each}
            </div>
          </div>
          <label><span>First programmable memory</span><input type="number" min="0" value={selectedRadio.memoryStart} oninput={(event) => updateRadio({ memoryStart: event.currentTarget.valueAsNumber })} /></label>
          <label class="check-field"><input type="checkbox" checked={selectedRadio.mapSetsToBanks} onchange={(event) => updateRadio({ mapSetsToBanks: event.currentTarget.checked })} /><span>Map selected sets to radio banks when supported</span></label>
          <label class="full"><span>Notes</span><textarea rows="4" value={selectedRadio.notes} oninput={(event) => updateRadio({ notes: event.currentTarget.value })}></textarea></label>
        </div>

        {#if selectedModel}
          <div class="model-facts">
            <div><span>Memory capacity</span><strong>{selectedModel.memory_capacity}</strong></div>
            <div><span>Label length</span><strong>{selectedModel.max_label_length}</strong></div>
            <div><span>Banks</span><strong>{selectedModel.supports_banks ? selectedModel.bank_count : "None"}</strong></div>
          </div>

          <div class="factory-section">
            <div class="inspector-section-heading"><h3>Factory-provided frequency sets</h3><span>{selectedModel.factory_frequency_sets.length}</span></div>
            {#if selectedModel.factory_frequency_sets.length === 0}
              <p class="empty-copy">No verified factory frequency sets are recorded for this model.</p>
            {:else}
              {#each selectedModel.factory_frequency_sets as relation (relation.frequency_set_id)}
                <article class="factory-card">
                  <div><strong>{relation.frequency_set_name}</strong><small>{relation.frequency_set_id}</small></div>
                  <span class="record-badge badge--preset">{relation.interface_label}</span>
                  <dl><div><dt>Frequency editing</dt><dd>{relation.frequency_editing}</dd></div><div><dt>CHIRP editing</dt><dd>{relation.chirp_editing}</dd></div></dl>
                </article>
              {/each}
            {/if}
          </div>
        {/if}
      </section>
    </div>
  {/if}
</main>
