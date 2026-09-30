<script lang="ts">
	// A row of cards, and only as many as fit across the screen at once.
	//
	// A row you have to walk along is a shelf pretending to be a glance — and the
	// shelf is one press away, holds all of it, and can be put in any order you
	// like. So the row shows what a look at the screen shows and stops there.
	//
	// The wall says how many that is — the same wall, the same cell, so a card
	// is one size wherever it is met. This is the one consumer that needs the
	// NUMBER and not only the track: a row is one line, and the extras must not
	// wrap into a second.

	import { Heading } from '$lib/kit';
	import Poster from '$lib/parts/Poster.svelte';
	import Wall from '$lib/tvui/Wall.svelte';
	import { POSTER, DESK_POSTER, MOBILE_POSTER } from '$lib/tvui/cells';
	import { surface } from '$lib/keep/surface.svelte';
	import { t, type MessageKey } from '$lib/i18n';
	import type { Row } from '$lib/keep/types';

	let { row, onpick }: { row: Row; onpick: (c: import('$lib/keep/types').Card) => void } = $props();

	const cell = $derived(surface.isTv ? POSTER : surface.isMobile ? MOBILE_POSTER : DESK_POSTER);
</script>

<section class:tv={surface.isTv} data-follow>
	<!-- rows the player names itself are translated; a row a catalogue named
	     arrives with the name it already has -->
	<Heading label={row.label ?? t(`row.${row.key}` as MessageKey)} />
	<Wall cell={cell.cell} gap={cell.gap} rowGap={cell.rowGap}>
		{#snippet children(across)}
			{#each row.cards.slice(0, across) as card ((card.owned === false ? 'tmdb:' : '') + card.kind + card.id)}
				<div class="slot" class:round={card.round} class:square={card.square}>
					<Poster {card} {onpick} />
				</div>
			{/each}
		{/snippet}
	</Wall>
</section>

<style>
	/* No ground of its own: the thing being looked at is the ground, and a row
	   of posters lies on it. */
	section {
		margin-bottom: 1.4rem;
	}
	.slot {
		min-width: 0;
	}
	.tv {
		margin-bottom: 1.8rem;
	}
	/* the row a card is being chosen from is the one being looked at */
	.tv :global(.wall:focus-within .card:not(:focus-visible) .art) {
		opacity: 0.5;
		transition: opacity 140ms ease;
	}
</style>
