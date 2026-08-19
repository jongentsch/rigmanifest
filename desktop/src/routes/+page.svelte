<script lang="ts">
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";

  onMount(() => {
    void goto("/compile", { replaceState: true });
  });
</script>

<main class="workspace">
  <section class="workspace-panel loading-panel" aria-live="polite">
    <span class="loading-indicator"></span>
    <div><strong>Opening RigManifest</strong><p>Loading your radio workspace.</p></div>
  </section>
</main>
