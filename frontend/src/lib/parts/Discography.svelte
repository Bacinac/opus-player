<script lang="ts">
	import { SvelteSet } from 'svelte/reactivity';
	import { art } from '$lib/ask/art';
	import { t } from '$lib/i18n';
	import { Progress, request, withLang } from '$lib/kit';
	import { wantRecord } from '$lib/ask/want';
	import Kin from '$lib/parts/Kin.svelte';
	import type { ArtistShelf, Card } from '$lib/keep/types';

	let {
		shelf,
		part = 'all',
		album,
		onalbum,
		onopen,
		onshelf
	}: {
		shelf: ArtistShelf;
		/** a television keeps the whole of this behind INFO but the shelf
		    itself: who is in the band, and what they made that we do not hold */
		part?: 'all' | 'aside';
		album: boolean;
		onalbum: (releaseId: number) => void;
		onopen?: (c: Card) => void;
		onshelf: (found: ArtistShelf) => void;
	} = $props();

	// Asked for from here, and said here. A record queued from a sofa gets no
	// dialogue asking whether that is really what was meant: what it costs is one
	// record, the queue next door is where it can be taken back, and a remote
	// that answers a question with another question is a remote nobody uses. The
	// tile saying it is on its way IS the confirmation.
	let queued = $state(new SvelteSet<number>());

	async function askFor(record: { id: number; title: string }) {
		if (!(await wantRecord(record.id))) return;
		queued = new SvelteSet([...queued, record.id]);
	}

	/** While anything on this page is on its way, ask again — a bar that does not
	 *  move is worse than no bar. Only while: an artist nobody is fetching
	 *  anything for is a page that never speaks to the server again. */
	$effect(() => {
		const id = shelf.id;
		if (!shelf.missing.some((r) => r.coming) && queued.size === 0) return;
		const stop = new AbortController();
		// a beat that is missed is followed by the next one
		const timer = setInterval(() => {
			void request<ArtistShelf>(withLang(`/api/library/artist/${id}`), { signal: stop.signal }, {
				failed: () => {}
			}).then((found) => found && onshelf(found));
		}, 4000);
		return () => {
			clearInterval(timer);
			stop.abort();
		};
	});
</script>

{#if !album}
	<Kin label={t('sheet.members')} who={shelf.members} {onopen} />
	<Kin label={t('sheet.groups')} who={shelf.groups} {onopen} />
{/if}
{#if part === 'all' && shelf.releases.length}
<div class="shelf discography">
	{#each shelf.releases as r (r.id)}
		<button class="record" onclick={() => onalbum(r.id)}>
			{#if r.cover}<img src={art(r.cover, 320)} alt="" />{/if}
			<span class="name">{r.title}</span>
			<span class="tag">{r.year}</span>
		</button>
	{/each}
</div>
{/if}
<!-- The second row, and it is a row rather than a list because
     down is already how a remote leaves the first one. What is
     here has no cover on the shelf and no songs behind it, so
     it is drawn faint: the difference between the two rows has
     to be legible from a sofa without reading either. -->
{#if shelf.missing.length}
	<h3 class="absent">{t('sheet.missing')}</h3>
	<div class="shelf">
		{#each shelf.missing as r (r.id)}
			{@const onItsWay = r.coming || queued.has(r.id)}
			<button class="record faint" disabled={onItsWay} onclick={() => askFor(r)}>
				{#if r.cover}<img src={art(r.cover, 320)} alt="" />{/if}
				<span class="name">{r.title}</span>
				{#if onItsWay && r.progress != null}
					<!-- how far it has got, said as the bar rather than as a
					     number: from a sofa the shape is read and the digits
					     are not -->
					<Progress value={r.progress} />
				{:else}
					<span class="tag">{onItsWay ? t('sheet.coming') : r.year}</span>
				{/if}
			</button>
		{/each}
	</div>
{/if}

<style>
	/* The first row of covers sat against whatever was above it — a list of the
	   band, or the songs of the record just opened — near enough to read as more
	   of that thing. The rule belongs to the discography rather than to what
	   happens to precede it, which is why an opened record had no line at all:
	   the names it was hung on are not drawn there. */
	.discography {
		margin-top: 1.6rem;
		padding-top: 1.6rem;
		border-top: 1px solid var(--border);
	}
	/* Two lines, the same as every other tile in the app. On one line the
	   ellipsis fell inside the title of two records out of five — the average
	   name on this shelf is twenty-three characters and the cell holds far
	   fewer, so `Pistaccio Meta…` was the rule rather than the exception. */
	.name {
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		line-height: 1.25;
		overflow-wrap: anywhere;
	}
	.tag {
		font-size: 0.85em;
		color: var(--muted);
	}
	.shelf {
		display: grid;
		/* the poster cell, as cells.ts states it — this was the one wall that
		   already behaved across the level change, so only the spelling moves */
		grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
		gap: 0.8rem;
	}
	.record {
		display: grid;
		gap: 0.15rem;
		padding: 0;
		border: none;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	/* Faint says what the row is without a word: no cover on the shelf, nothing
	   behind it to play. It has to read from a sofa, so it is the picture that
	   is dimmed and not the writing — a name nobody can make out is not
	   restraint, it is a name nobody can make out. */
	.record.faint img {
		opacity: 0.45;
	}
	.record.faint:hover img,
	.record.faint:focus-visible img {
		opacity: 0.75;
	}
	.record.faint:disabled {
		cursor: default;
	}
	.absent {
		margin: 1.2rem 0 0.5rem;
		font-size: var(--fs-l);
		font-weight: 600;
		color: var(--muted);
	}
	.record img {
		width: 100%;
		aspect-ratio: 1;
		object-fit: cover;
		border-radius: var(--radius-s);
		margin-bottom: 0.25rem;
	}
	.record .name {
		font-size: 0.9em;
	}
	h3 {
		margin: 0.3rem 0 0.6rem;
	}
</style>
