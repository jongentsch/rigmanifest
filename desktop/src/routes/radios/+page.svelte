<script lang="ts">
  import { onMount } from "svelte";

  import { loadCatalog } from "$lib/api";
  import {
    createRadioInstance,
    loadRadioInventory,
    saveRadioInventory,
  } from "$lib/radios";
  import type { RadioInstance, RadioModelRecord, WorkspaceCatalog } from "$lib/types";

  let catalog = $state<WorkspaceCatalog | null>(null);
  let radios = $state<RadioInstance[]>([]);
  let selectedRadioId = $state("");
  let failure = $state("");
  let saved = $state(false);

  let selectedRadio = $derived(radios.find((item) => item.id === selectedRadioId) ?? null);
  let selectedModel = $derived(
    catalog?.radio_models.find((item) => item.id === selectedRadio?.radioModelId) ?? null,
  );

  onMount(async () => {
    try {
      catalog = await loadCatalog();
      radios = loadRadioInventory();
      selectedRadioId = radios[0]?.id ?? "";
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
    saved = false;
  }

  function removeRadio(): void {
    if (radios.length <= 1) return;
    const remaining = radios.filter((item) => item.id !== selectedRadioId);
    radios = remaining;
    selectedRadioId = remaining[0]?.id ?? "";
    saveRadioInventory(radios);
  }

  function persist(): void {
    saveRadioInventory(radios);
    saved = true;
  }

  function changeModel(event: Event): void {
    const radioModelId = (event.currentTarget as HTMLSelectElement).value;
    const model = catalog?.radio_models.find((item) => item.id === radioModelId);
    updateRadio({
      radioModelId,
      memoryStart: model?.memory_start ?? selectedRadio?.memoryStart ?? 1,
    });
  }

  function errorMessage(error: unknown): string {
    if (typeof error === "string") return error;
    if (error instanceof Error) return error.message;
    return "The radio inventory could not be loaded.";
  }

  function modelLabel(model: RadioModelRecord): string {
    return `${model.manufacturer} ${model.model}`;
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
              onclick={() => selectedRadioId = radio.id}
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
          <label><span>Radio model</span><select value={selectedRadio.radioModelId} onchange={changeModel}>{#each catalog.radio_models as model}<option value={model.id}>{modelLabel(model)}</option>{/each}</select></label>
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
