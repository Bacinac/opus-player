<script lang="ts">
	// A page about one thing that holds parts: its parts down the left as pills,
	// and what the part the remote stands on holds beside them — a series'
	// seasons and their episodes, an artist's records and their songs. Landing on
	// a part shows it; there is no level to go into and come back out of. The
	// parts are a column and not a row across the top: a row of a long series
	// wrapped into lines that left the screen one episode.

	import type { Snippet } from 'svelte';
	import { fill } from './fill';

	let {
		parts,
		held,
		rows = $bindable(null)
	}: {
		/** the pills, and under them what may be done about the one in force */
		parts: Snippet;
		/** what the part in force holds */
		held: Snippet;
		/** the scrolling side, for a page that starts another part at its top */
		rows?: HTMLElement | null;
	} = $props();
</script>

<div class="split">
	<div class="scrub parts" role="group" data-lands use:fill>
		{@render parts()}
	</div>
	<div class="rows" bind:this={rows} use:fill>
		{@render held()}
	</div>
</div>

<style>
	.split {
		display: grid;
		grid-template-columns: minmax(12rem, 16rem) 1fr;
		gap: 1.5rem;
		/* the columns' padding is room for the ring, not an indent */
		margin-left: -0.4rem;
	}
	.parts {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		/* level with the picture of the first row, which stands inside its own
		   padding */
		padding: 0.95rem 0.4rem 1rem;
		overflow-y: auto;
		scrollbar-width: none;
	}
	.parts :global(.press) {
		display: flex;
		align-items: center;
		text-align: left;
		flex: none;
	}
	/* the part's own actions stand apart from the parts they act on */
	.parts :global(.press:not(.pill)) {
		margin-top: 0.4rem;
	}
	/* what a pill says after its name keeps to the far edge, in the pill's own
	   colour, so it stays legible on the one in force */
	.parts :global(.counts) {
		margin-left: auto;
		padding-left: 0.5rem;
		--tag-font: var(--fs-s);
		opacity: 0.8;
	}
	.parts :global(.counts *) {
		color: inherit;
	}
	/* only the rows move: the thing and its parts stay where the eye left them */
	.rows {
		display: grid;
		align-content: start;
		gap: 0.4rem;
		padding: 0.4rem 0.3rem 1rem;
		overflow-y: auto;
		scrollbar-width: none;
	}
</style>
