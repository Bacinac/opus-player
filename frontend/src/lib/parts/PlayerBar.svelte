<script lang="ts">
	// The bar every player uses.
	//
	// A record and a film are played by different engines and shown on different
	// screens, but the thing a person operates is the same object in both: what
	// is on, where it has got to, the keys, and whatever that medium adds — where
	// the sound goes for a record, the languages for a film. It was two bars with
	// two grounds, two paddings and two ideas of what a key looks like.
	//
	// Audio keeps it open for as long as something is playing. A film's is a
	// visit: it comes when it is asked for and leaves a few seconds later, which
	// is the one thing that differs and is said by `away`.

	import type { Snippet } from 'svelte';
	import Transport from '$lib/parts/Transport.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { t } from '$lib/i18n';
	import { Icon } from '$lib/kit';
	import Press from '$lib/tvui/Press.svelte';

	let {
		art = null,
		title = '',
		subtitle = '',
		position,
		total,
		going,
		toggle,
		seek,
		prev,
		next,
		hasNext = true,
		seekable = true,
		away = false,
		ends = '',
		onopen,
		extras,
		onclose
	}: {
		art?: string | null;
		title?: string;
		subtitle?: string;
		/** absent for something shown rather than played: the bar is then what
		 *  it is and the way out of it */
		position?: number;
		total?: number;
		going?: boolean;
		toggle?: () => void;
		seek?: (to: number) => void;
		prev?: () => void;
		next?: () => void;
		hasNext?: boolean;
		seekable?: boolean;
		/** a film's bar, gone until it is asked for */
		away?: boolean;
		ends?: string;
		/** pressing what is playing opens the screen about it */
		onopen?: () => void;
		extras?: Snippet;
		onclose?: () => void;
	} = $props();
	let tall = $state(0);

	$effect(() => {
		const root = document.documentElement;
		root.style.setProperty('--tv-bar-h', `${tall}px`);
		return () => root.style.removeProperty('--tv-bar-h');
	});
</script>

<!-- Its own height, written onto the document. What must clear this bar — the
     page's bottom padding, where a row lands when it is scrolled to — is a
     sibling and cannot read a property that inherits downwards, and a literal
     kept in step by hand is a literal that stops being in step. -->
<div
	class="bar"
	class:away
	class:opens={onopen !== undefined}
	class:still={!toggle}
	class:tv={surface.isTv}
	bind:clientHeight={tall}
	style:--tv-bar-h="{tall}px"
>
	{#if title}
		{#if onopen}
			<button class="what" onclick={onopen}>
				{#if art}<img class="art" src={art} alt="" />{/if}
				<span class="said">
					<span class="title">{title}</span>
					{#if subtitle}<span class="who">{subtitle}</span>{/if}
				</span>
			</button>
		{:else}
			<span class="what">
				{#if art}<img class="art" src={art} alt="" />{/if}
				<span class="said">
					<span class="title">{title}</span>
					{#if subtitle}<span class="who">{subtitle}</span>{/if}
				</span>
			</span>
		{/if}
	{/if}

	<!-- Everything after the line is one row of keys: what the medium adds, and
	     then the way out of it. Standing the close key in a column of its own gave
	     one bar a key at the screen's edge and the other a key beside the clock,
	     which is two bars again. -->
	{#snippet keys()}
		{#if extras}{@render extras()}{/if}
		{#if onclose}
			<Press tone="key" onclick={onclose} label={t('common.close')}>
				<Icon name="close" size={16} />
			</Press>
		{/if}
	{/snippet}

	{#if toggle && seek}
		<Transport
			position={position ?? 0}
			total={total ?? 0}
			going={going ?? false}
			{toggle}
			{seek}
			{prev}
			{next}
			{hasNext}
			{seekable}
			barFocusable={!surface.isTv}
			small
			{ends}
			extras={keys}
		/>
	{:else}
		<div class="keys">{@render keys()}</div>
	{/if}
</div>

<style>
	/* Across the page, edge to edge, along the bottom: what is playing is
	   playing wherever you go, so this is the floor of every screen rather than
	   a card lying on one. It keeps the ground and the hairline the cards are
	   drawn with, as one line along its top. */
	.bar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 24;
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.7fr);
		align-items: center;
		gap: 0.9rem;
		padding: 0.55rem 1rem;
		border-top: var(--card-line, 1px solid var(--on-picture-faint));
		/* the app's own ground, not whatever is behind it: a card may be
		   translucent over fanart, but the floor of the screen lies over a
		   picture as well, and a bar you cannot read over a bright frame is a
		   bar that only works on dark films */
		background: color-mix(in srgb, var(--bg, var(--surface)) 92%, transparent);
		backdrop-filter: blur(16px);
		transition: opacity 160ms ease;
	}
	/* Ten feet away every key is wider than on a desk, and a key pushed past
	   the edge of the screen cannot be reached. The keys take what they need,
	   the line keeps a short run of its own, and what is playing gets the rest. */
	.bar.tv {
		grid-template-columns: minmax(10rem, 1fr) minmax(0, max-content);
		padding: 0.6rem var(--tenfoot-pad, 3rem) var(--tenfoot-safe-y, 1.7rem);
	}
	.bar.tv :global(.transport input) {
		flex: 1 1 4rem;
	}
	/* a film's bar between visits: gone, and unreachable while it is gone */
	.keys {
		display: flex;
		justify-self: end;
		gap: 0.4rem;
	}
	.bar.away {
		opacity: 0;
		pointer-events: none;
	}
	.what {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		min-width: 0;
		padding: 0.2rem 0.3rem;
		border: none;
		border-radius: var(--radius-s);
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	button.what:hover,
	button.what:focus-visible {
		background: color-mix(in srgb, currentColor 10%, transparent);
		outline: none;
	}
	.art {
		width: 2.6rem;
		height: 2.6rem;
		border-radius: var(--radius-s);
		object-fit: cover;
	}
	.said {
		display: grid;
		min-width: 0;
	}
	.said span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.title {
		font-weight: 600;
	}
	.who {
		font-size: 0.85em;
		color: var(--muted);
	}
	/* Every key a medium adds to the bar — the words, the languages, where the
	   sound goes — is drawn the way the transport's own keys are. A row of
	   controls in one bar is one row. */
	.bar :global(.transport .key) {
		font-size: var(--fs-l);
		letter-spacing: 0.02em;
	}
	/* A narrow screen has room for the line or for the keys, not for both in
	   one row. A record's bar gives up the line, because pressing it opens the
	   screen that has one; a film's bar is the only way through the film, so it
	   keeps the line, on a row of its own above the keys. */
	@media (max-width: 700px) {
		.bar {
			grid-template-columns: minmax(0, 1fr) auto;
		}
		.bar.opens :global(.transport input),
		.bar.opens :global(.transport .time) {
			display: none;
		}
		.bar:not(.opens) {
			grid-template-columns: minmax(0, 1fr);
			gap: 0.3rem;
		}
		.bar:not(.opens) :global(.transport) {
			flex-wrap: wrap;
			row-gap: 0.2rem;
		}
		.bar:not(.opens) :global(.transport .time),
		.bar:not(.opens) :global(.transport input) {
			order: -1;
		}
		.bar:not(.opens) :global(.transport .time) {
			flex: 0 0 3.2rem;
		}
		.bar:not(.opens) :global(.transport input) {
			flex: 1 1 calc(100% - 7.6rem);
		}
		.bar:not(.opens) :global(.transport .ends) {
			order: 1;
		}
		.bar.still {
			grid-template-columns: minmax(0, 1fr) auto;
		}
	}
</style>
