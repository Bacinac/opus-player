<script lang="ts">
	// Plain rows, each one label and one control: a `.row` holding a `.what` and
	// whatever answers it. A remote walks a column of boxes; anything cleverer
	// than that it walks past.

	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<div class="rows">
	{@render children()}
</div>

<style>
	.rows {
		display: grid;
		/* two columns rather than rows each pushing its own control at the
		   far edge of however wide the window happens to be: the labels end
		   where the widest of them ends, and every control starts there. */
		grid-template-columns: max-content max-content;
		gap: 0.45rem 1.2rem;
		align-items: center;
	}
	.rows :global(.row) {
		display: contents;
	}
	.rows :global(.row > .what) {
		color: var(--muted);
		font-size: var(--fs-m);
	}
	.rows :global(.row > .what em) {
		font-style: normal;
		opacity: 0.75;
		margin-left: 0.4rem;
	}
</style>
