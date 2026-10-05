<script lang="ts">
	import { onMount } from 'svelte';
	import Dialog from '$lib/kit/Dialog.svelte';
	import { goBack, onBack } from './back.svelte';
	let outer = $state(false);
	let inner = $state(false);
	let navigations = $state(0);
	onMount(() => {
		const drop = onBack(() => { navigations++; return true; });
		const key = (event: KeyboardEvent) => {
			if (event.key === 'Escape' && goBack()) event.preventDefault();
		};
		window.addEventListener('keydown', key);
		return () => { drop(); window.removeEventListener('keydown', key); };
	});
</script>

<button onclick={() => (outer = true)}>Open dialog</button>
<output>{navigations}</output>
{#if outer}
	<Dialog title="Outer" onclose={() => (outer = false)}>
		<button onclick={() => (inner = true)}>Open nested dialog</button>
	</Dialog>
{/if}
{#if inner}
	<Dialog title="Inner" onclose={() => (inner = false)}>
		<span>Preview</span>
	</Dialog>
{/if}
