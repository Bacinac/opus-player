<script lang="ts" generics="T">
	// A list on the left and, beside it, the one thing in it the remote is on.
	//
	// The shape a ten-foot skin gives anything read one line at a time — an
	// artist's records, a season's episodes, the countries the house has been
	// to. A wall of covers asks the eye to find its place among twenty pictures
	// at once; a list asks only up or down, and the picture and the paragraph
	// are about the line under the ring, so there is exactly one of them.
	//
	// Only the list moves. It scrolls inside the height left to it under
	// whatever head the page wears, and the side stays where it is.

	import type { Snippet } from 'svelte';
	import { fill } from './fill';

	let {
		items,
		key,
		line,
		aside,
		onpick,
		onat,
		faded,
		perch,
		at = $bindable(null)
	}: {
		items: T[];
		key: (item: T) => string | number;
		/** what the line says */
		line: Snippet<[T]>;
		/** what is said beside the list about the line the remote is on */
		aside: Snippet<[T]>;
		onpick: (item: T) => void;
		/** the remote arrived on a line, for a side that has to ask about it */
		onat?: (item: T) => void;
		/** a line that is there to be known about rather than opened */
		faded?: (item: T) => boolean;
		/** the play key's address for a line, when a line can be put on */
		perch?: (item: T) => string | undefined;
		/** the key of the line the remote is on */
		at?: string | number | null;
	} = $props();

	const current = $derived(items.find((one) => key(one) === at) ?? items[0]);

	function land(one: T) {
		at = key(one);
		onat?.(one);
	}
</script>

<div class="ledger" use:fill>
	<ul class="lines">
		{#each items as one (key(one))}
			<li>
				<button
					class="line"
					class:faded={faded?.(one)}
					class:at={current && key(current) === key(one)}
					data-key={key(one)}
					data-perch={perch?.(one)}
					onfocus={() => land(one)}
					onmouseenter={() => land(one)}
					onclick={() => onpick(one)}
				>
					{@render line(one)}
				</button>
			</li>
		{/each}
	</ul>
	<div class="aside" aria-live="polite">
		{#if current}{@render aside(current)}{/if}
	</div>
</div>

<style>
	.ledger {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
		gap: 2rem;
		min-height: 0;
	}
	.lines {
		list-style: none;
		margin: 0;
		padding: 0.25rem 0.4rem 1rem 0.25rem;
		overflow-y: auto;
		min-height: 0;
		scrollbar-width: none;
	}
	.line {
		display: flex;
		align-items: baseline;
		gap: 0.8rem;
		width: 100%;
		padding: 0.5rem 0.8rem;
		border: none;
		border-radius: var(--radius-s, 8px);
		background: transparent;
		color: var(--muted);
		font: inherit;
		font-size: var(--fs-l);
		text-align: left;
		cursor: pointer;
	}
	.line.at {
		color: var(--text);
	}
	.line:hover,
	.line:focus-visible {
		color: var(--bright, var(--text));
		background: color-mix(in srgb, currentColor 12%, transparent);
		outline: none;
	}
	/* there to be known about: the line is dimmed, and the words stay legible */
	.line.faded {
		opacity: 0.5;
	}
	.line.faded:focus-visible {
		opacity: 0.8;
	}
	/* the pieces a line is made of, named once so every list lays them alike */
	.line :global(.main) {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 600;
	}
	.line :global(.lead),
	.line :global(.side) {
		flex: none;
		font-size: 0.85em;
		font-variant-numeric: tabular-nums;
		color: var(--muted);
	}
	/* the picture gives way to the words: it shrinks, they do not */
	.aside {
		min-height: 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.aside > :global(*) {
		flex: none;
	}
	.aside :global(img.picture) {
		flex: 0 1 auto;
		min-height: 4rem;
		width: 100%;
		aspect-ratio: 16 / 9;
		object-fit: cover;
		border-radius: var(--card-radius, 12px);
		box-shadow: var(--poster-shadow);
		background: var(--surface);
	}
	.aside :global(img.picture.square) {
		width: min(11rem, 36vh);
		height: auto;
		max-height: none;
		aspect-ratio: 1;
	}
	.aside :global(img.picture.poster) {
		width: min(9rem, 30vh);
		height: auto;
		max-height: none;
		aspect-ratio: 2 / 3;
	}
	/* a square picture and its words side by side: a cover stacked over its
	   paragraph leaves the paragraph no room on a screen 540 points tall */
	.aside :global(.beside) {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 1.1rem;
		align-items: start;
	}
	.aside :global(.beside > div) {
		display: grid;
		gap: 0.5rem;
		min-width: 0;
	}
	.aside :global(h3) {
		margin: 0;
		font-size: var(--fs-xl);
		color: var(--bright, var(--text));
	}
	.aside :global(.facts) {
		margin: 0;
		color: var(--muted);
		font-size: var(--fs-m);
		font-variant-numeric: tabular-nums;
	}
	.aside :global(.said) {
		margin: 0;
		font-size: var(--fs-m);
		line-height: 1.45;
		display: -webkit-box;
		-webkit-line-clamp: var(--said-lines, 6);
		line-clamp: var(--said-lines, 6);
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
</style>
