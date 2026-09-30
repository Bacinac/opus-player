<script lang="ts">
	// One kind of thing, all of it, wrapped. What a row is when you have stopped
	// browsing and started looking for something in particular.
	//
	// The wall decides how many fit; this file only says how wide a poster is on
	// each surface and keeps the one rule that is a poster wall's own — the rest
	// stepping back while something is being chosen.

	import Poster from '$lib/parts/Poster.svelte';
	import Wall from '$lib/tvui/Wall.svelte';
	import { POSTER, DESK_POSTER, MOBILE_POSTER } from '$lib/tvui/cells';
	import { surface } from '$lib/keep/surface.svelte';
	import type { Card as CardType } from '$lib/keep/types';

	let { cards, onpick }: { cards: CardType[]; onpick: (c: CardType) => void } = $props();

	const cell = $derived(surface.isTv ? POSTER : surface.isMobile ? MOBILE_POSTER : DESK_POSTER);
</script>

<div class="grid" class:tv={surface.isTv}>
	<Wall cell={cell.cell} gap={cell.gap} rowGap={cell.rowGap} bleed={surface.isTv}>
		{#snippet children(_across)}
			{#each cards as card ((card.owned === false ? 'tmdb:' : '') + card.kind + card.id)}
				<Poster {card} {onpick} />
			{/each}
		{/snippet}
	</Wall>
</div>

<style>
	/* Ten feet away the eye needs one thing to land on, so the rest step back
	   while something is being chosen. */
	.tv:focus-within :global(.card:not(:focus-visible) .art) {
		opacity: 0.5;
		transition: opacity 140ms ease;
	}
</style>
