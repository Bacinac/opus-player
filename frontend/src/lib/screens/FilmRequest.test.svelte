<script lang="ts">
	import { film } from '$lib/keep/film.svelte';
	import Play from './Play.svelte';
</script>

{#if film.asked}
	{#key `${film.asked.kind}:${film.asked.id}`}
		<Play card={film.asked} onclose={() => film.close()} />
	{/key}
{/if}
