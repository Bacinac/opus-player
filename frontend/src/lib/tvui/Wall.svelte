<script lang="ts">
	// As many across as fit. A wall declares how wide ONE thing wants to be; the
	// count is not ours to state — it is what the room answers, and the room is
	// 665 points beside the menu and 880 without it. Declaring a count was the
	// trap this replaces: the same shelf drew a 120-point poster on one level
	// and a 163-point one on the other, two of our own screens disagreeing.
	//
	// CSS lays out; JS only publishes the number. The auto-fill track paints
	// correctly on the first frame with no measurement — bind:clientWidth exists
	// solely so a ROW can slice its list to one line. The two cannot disagree
	// because they are the same arithmetic, the one PhotoTimeline already runs.

	import type { Snippet } from 'svelte';

	let {
		cell = 96,
		gap = 16,
		rowGap = gap,
		bleed = false,
		children
	}: {
		/** how wide one thing wants to be, in px — a token from cells.ts */
		cell?: number;
		/** the air between columns, in px */
		gap?: number;
		/** the air between rows; the column gap unless a wall says otherwise */
		rowGap?: number;
		/** room for the focus ring to stand in, paid back on the outside so the
		 *  track keeps the container's width — a poster wall wants it, a mosaic
		 *  with 3px gutters must not have it */
		bleed?: boolean;
		children: Snippet<[number]>;
	} = $props();

	let width = $state(0);
	const across = $derived(Math.max(1, Math.floor((width + gap) / (cell + gap))));
</script>

<div
	bind:clientWidth={width}
	class="wall"
	class:bleed
	style:--cell="{cell}px"
	style:--gap-x="{gap}px"
	style:--gap-y="{rowGap}px"
>
	{@render children(across)}
</div>

<style>
	.wall {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(var(--cell), 1fr));
		gap: var(--gap-y) var(--gap-x);
	}
	.bleed {
		padding: 0.8rem 0.8rem 2.5rem;
		margin: -0.8rem -0.8rem 0;
	}
</style>
