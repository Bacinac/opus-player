<script lang="ts">
	// One thing you can watch or listen to. The same card on every surface —
	// what changes is its size and whether it can be focused with a remote,
	// because a poster is a poster whether you are pointing at it or arrowing
	// onto it from the one beside it.

	import { surface } from '$lib/keep/surface.svelte';
	import { hero } from '$lib/keep/hero.svelte';
	import { preview } from '$lib/keep/preview.svelte';
	import { art } from '$lib/ask/art';
	import { Icon } from '$lib/kit';
	import { StateMark, episodeCode, videoStateMark } from '$lib/opus';
	import { formatNumber, t } from '$lib/i18n';
	import type { Card } from '$lib/keep/types';

	let { card, onpick }: { card: Card; onpick: (c: Card) => void } = $props();

	// The widest a card is ever drawn: five across a television is three hundred
	// device pixels, and a phone's three columns on a doubled panel is the same
	// number again. One size for every surface, because it is the same number.
	const POSTER = 320;

	const progress = $derived(
		card.position_s && card.duration_s ? card.position_s / card.duration_s : 0
	);

	const src = $derived(card.image ? art(card.image, POSTER) : '');
	const services = $derived(
		card.owned === false
			? (card.streaming ?? [])
					.filter((s) => s.logo)
					.sort((a, b) => Number(b.ours) - Number(a.ours))
					.slice(0, 3)
			: []
	);
</script>

<button
	data-card={card.id}
	data-perch="{card.kind}:{card.id}"
	class="card"
	class:round={card.round}
	class:logo={card.kind === 'station'}
	class:square={card.square}
	class:tv={surface.isTv}
	onclick={() => onpick(card)}
	onfocus={(event) => {
		preview.clear();
		// focus the shelf handed back rather than focus somebody moved: the head
		// goes on saying what the shelf is. Read off the tile itself, because a
		// flag set beforehand loses the race with whatever else the closing
		// panel does on its way out — sometimes the shelf came back titled with
		// the artist that had just been closed, and sometimes it did not.
		if ((event.currentTarget as HTMLElement).dataset.returned === undefined) {
			hero.show(card);
		}
	}}
>
	<div class="art">
		{#if card.image}
			<img src={src} alt="" loading="lazy" />
		{:else}
			<span class="fallback">{card.title.slice(0, 1)}</span>
		{/if}
		{#if progress > 0}
			<span class="bar"><span class="fill" style={`width:${progress * 100}%`}></span></span>
		{/if}
		{#if card.badge}<span class="badge" class:owned={card.owned}>{card.badge}</span>{/if}
		{#if card.kind === 'episode' && card.season_number !== undefined && card.number !== undefined}
			<span class="code">{episodeCode(card.season_number, card.number)}</span>
		{/if}
		{#if card.seen}
			<span class="seen" title={t('series.seen')}><Icon name="check" size={12} />{card.seen > 1 ? formatNumber(card.seen) : ''}</span>
		{/if}
		{#if card.state === 'waiting_subtitles'}
			<span class="warn"><StateMark {...videoStateMark(card.state)!} size={14} text={t('card.waitingSubtitles')} /></span>
		{/if}
		{#if services.length}
			<span class="services">
				{#each services as service (service.id)}
					<img
						class="service"
						class:ours={service.ours}
						src={art(service.logo, 160)}
						alt={service.name}
						title={service.name}
					/>
				{/each}
			</span>
		{/if}
	</div>
	<!-- Title and what is under it are one block. The year belongs to the name it
	     is under, not to the bottom of a box: reserving the height on the title
	     itself pushed a year a whole empty line away whenever the name fitted on
	     one, which is most of them. -->
	<span class="label">
		<span class="title">{card.title}</span>
		{#if card.subtitle}<span class="sub">{card.subtitle}</span>{/if}
	</span>
</button>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		padding: 0;
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
		/* the width is the row's business, not the card's */
		width: 100%;
	}
	.art {
		position: relative;
		aspect-ratio: 2 / 3;
		border-radius: var(--radius-m);
		overflow: hidden;
		background: var(--surface-2);
		display: grid;
		place-items: center;
	}
	/* a record sleeve is square and always has been; cropping one to the shape
	   of a film poster cuts the title off both sides */
	.square .art {
		aspect-ratio: 1;
	}
	.round .art {
		aspect-ratio: 1;
		border-radius: 50%;
	}
	/* A station's picture is a logo, not a sleeve: some come as white marks on
	   white, some as full-bleed artwork, and cropping them all to fill left a
	   shelf where every tile had a different edge and a different ground. They
	   are set whole on one ground with air around them, so the shelf reads as
	   one row of stations rather than a wall of other people's design. */
	.logo .art {
		aspect-ratio: 1;
		background: var(--logo-ground);
		padding: 12%;
		box-sizing: border-box;
	}
	.logo img {
		object-fit: contain;
	}
	img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.fallback {
		font-size: 2rem;
		font-weight: 700;
		color: var(--muted);
	}
	.label {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.title {
		font-size: var(--fs-m);
		line-height: 1.25;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}
	.round .label {
		align-items: center;
	}
	.round .title,
	.round .sub {
		text-align: center;
	}
	.sub {
		font-size: var(--fs-s);
		color: var(--muted);
	}
	.bar {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		height: 3px;
		background: color-mix(in srgb, var(--bg) 60%, transparent);
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	/* the opposite corner to whatever the catalogue put on the poster: one is
	   about the copy and this one is about the person looking at it */
	.seen,
	.code {
		position: absolute;
		top: 0.35rem;
		left: 0.35rem;
		display: inline-flex;
		align-items: center;
		gap: 0.1rem;
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--ok) 90%, transparent);
		color: var(--bg);
		font-size: var(--fs-xs);
		font-weight: 700;
	}
	/* which episode, where a poster only says which series */
	.code {
		padding: 0.1rem 0.5rem;
		background: color-mix(in srgb, var(--bg) 85%, transparent);
		color: var(--text);
		font-size: var(--fs-s);
	}
	.badge,
	.warn {
		position: absolute;
		top: 0.35rem;
		right: 0.35rem;
		display: flex;
		padding: 2px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--bg) 78%, transparent);
	}
	.warn {
		color: var(--warn);
	}
	/* among things found in the world, the ones already on the shelf are the
	   ones the eye must find first */
	.badge.owned {
		padding: 0.1rem 0.5rem;
		background: var(--accent);
		color: var(--bg);
		font-size: var(--fs-s);
		font-weight: 700;
		box-shadow: var(--shadow-s);
	}
	.services {
		position: absolute;
		left: 0.35rem;
		bottom: 0.35rem;
		display: flex;
		gap: 0.3rem;
	}
	.service {
		width: 1.6rem;
		height: 1.6rem;
		border-radius: 0.4rem;
		box-shadow: var(--shadow-s);
	}
	.service.ours {
		outline: 2px solid var(--ok);
		outline-offset: 1px;
	}

	/* Ten feet away there is no pointer, so the only thing that can say "this
	   one" is the focus ring — and it has to be unmissable, not tasteful. */
	.card:focus-visible {
		outline: none;
	}
	/* A pointer gets the same mark on the way BACK. `:focus-visible` is about
	   how focus was taken, and focus put there by the shelf itself was not
	   taken by a key — so the one moment somebody most needs to be told which
	   tile they came back to is the one moment the browser draws nothing. */
	.card:focus-visible .art {
		outline: var(--focus-ring);
		outline-offset: var(--focus-offset);
	}
	/* global, because the attribute is put on by the shelf at the moment it
	   hands the ring back — the compiler cannot see it in this markup and
	   would drop the rule as unused */
	:global(.card[data-returned]:focus .art) {
		outline: var(--focus-ring);
		outline-offset: var(--focus-offset);
	}
	.tv:focus-visible .art {
		outline-width: 4px;
		box-shadow: var(--shadow-l);
	}
	/* It does not grow at all any more. Whichever edge it grew from, it stood on
	   something: on the name of the shelf above it, on its own title, or on the
	   row underneath. A ring and the rest stepping back say which one has the
	   remote just as well, and nothing moves. */
	.tv:focus-visible {
		z-index: 2;
	}
	/* every poster stands on a shadow, chosen or not — the skin draws one around
	   all of them, and it is what keeps a wall of artwork off the flat ground */
	.tv .art {
		box-shadow: var(--poster-shadow, none);
		transition: opacity 140ms ease;
	}
	/* No name under the poster. Ten feet away a grid of titles is a page of
	   text with pictures in it — and the one name that matters is already being
	   said, in full and large, by the panel the remote is pointing at. Nothing
	   is lost and a row's worth of height is gained. */
	.tv .label {
		display: none;
	}
</style>
