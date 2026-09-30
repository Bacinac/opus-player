<script lang="ts">
	// This day, through the years it has been photographed.
	//
	// A timeline is read forwards and a person asks it one question it cannot
	// answer: what were we doing on this day. So this is not a third grid of
	// everything — it is one day, and the years are its rows.
	//
	// One request. The catalogue decides which day it is, because the day is the
	// household's wall clock and a browser sending its own idea of today would
	// file a photograph taken at half past eleven at night under the morning
	// after.

	import { thumbHashToDataURL } from 'thumbhash';
	import { cssUrl, request } from '$lib/kit';
	import { tileOf } from '$lib/opus';
	import PhotoViewer from '$lib/opus/PhotoViewer.svelte';
	import PhotoToTv from '$lib/parts/PhotoToTv.svelte';
	import type { Photo } from '$lib/keep/tvPhoto.svelte';
	import { askRecordings, recordingOf } from '$lib/ask/ability';
	import { formatDate, formatNumber, t } from '$lib/i18n';
	import { count } from '$lib/say/count';
	import { namesOf } from '$lib/say/says';
	import { surface } from '$lib/keep/surface.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { focusWaiting } from '$lib/tv/spatial.svelte';
	import Wall from '$lib/tvui/Wall.svelte';
	import { DESK_YEAR, YEAR } from '$lib/tvui/cells';

	type Shot = {
		id: string;
		kind: string;
		taken_at: string;
		w: number | null;
		h: number | null;
		hash: string | null;
		turn: number;
	};
	type Who = { id: number; name: string; faces: number };
	type Year = { year: number; people: Who[]; cover?: string; photographs: Shot[] };

	let years = $state<Year[]>([]);
	let asked = $state(false);
	let problem = $state('');
	/** which photograph is open, as a place in the year being read */
	let at = $state<number | null>(null);
	/** which year is open, if one is. The day is a shelf of years first: a
	 *  hundred and sixteen photographs from one afternoon are not what somebody
	 *  opening the photographs meant to be handed. */
	let year = $state<Year | null>(null);

	const shown = $derived(year?.photographs ?? []);
	const total = $derived(years.reduce((n, y) => n + y.photographs.length, 0));

	$effect(() => {
		void (async () => {
			const said = await request<{ years?: Year[] }>('/api/photos/onthisday', {}, {
				failed: (detail) => (problem = detail)
			});
			if (said) years = said.years ?? [];
			asked = true;
		})();
	});

	/** The 21 bytes the catalogue keeps draw the picture before its file has
	 *  left the disk. Without it a day of twenty years is twenty grey holes. */
	function ground(shot: Shot): string | undefined {
		const url = blur(shot);
		return url ? cssUrl(url) : undefined;
	}

	function blur(shot: Shot): string | undefined {
		if (!shot.hash) return undefined;
		try {
			return thumbHashToDataURL(
				Uint8Array.from(atob(shot.hash.replace(/-/g, '+').replace(/_/g, '/')), (c) =>
					c.charCodeAt(0)
				)
			);
		} catch {
			return undefined;
		}
	}

	const ago = (when: number) => new Date().getFullYear() - when;

	const about = (people: Who[]) => namesOf(people.map((one) => one.name));

	/** Hand the remote to what has just been drawn.
	 *
	 *  Waited for, and only after the frame that removes what it is leaving: the
	 *  lander stands down the moment anything holds the ring, and at the instant
	 *  a year is opened the thing holding it is the year being left. It goes,
	 *  focus falls to the document, and every arrow is dead — a day of
	 *  photographs nothing on the remote can reach. */
	function land(selector: string) {
		if (surface.isTv) setTimeout(() => focusWaiting(selector), 60);
	}

	function open(one: Year) {
		year = one;
		land('.shelf .tile');
	}

	// leaving a year is going back to the day, not out of the photographs
	$effect(() =>
		onBack(
			() => {
				if (at !== null) {
					const shot = shown[at]?.id;
					at = null;
					// back onto the picture that was open, not the first of a
					// hundred and sixteen
					land(`[data-shot="${CSS.escape(shot ?? '')}"]`);
					return true;
				}
				if (!year) return false;
				const was = year.year;
				year = null;
				land(`[data-year="${was}"]`);
				return true;
			},
			() => at !== null || !!year
		)
	);

	askRecordings();
</script>

{#if problem}
	<p class="quiet">{t('photos.dayFailed')}</p>
{:else if asked && !total}
	<p class="quiet">{t('photos.dayEmpty')}</p>
{:else}
	{#if !year}
		{@const wall = surface.isTv ? YEAR : DESK_YEAR}
		<Wall cell={wall.cell} gap={wall.gap}>
			{#snippet children(_across)}
			{#each years as one (one.year)}
				{@const cover = one.photographs.find((p) => p.id === one.cover) ?? one.photographs[0]}
				<button class="card" data-year={one.year} onclick={() => open(one)}>
					<span class="picture">
						{#if cover}
							<img
								src={tileOf(cover.id, cover.turn)}
								alt=""
								loading="lazy"
								style:background-image={ground(cover)}
							/>
						{/if}
					</span>
					<span class="said">
						<span class="when">
							{ago(one.year) === 0
								? t('photos.thisYear')
								: t('photos.yearsAgo', { n: formatNumber(ago(one.year)) })}
						</span>
						<span class="who">{about(one.people) || String(one.year)}</span>
						<span class="how-many">
							{one.year} · {count(one.photographs.length, 'photos').text}
						</span>
					</span>
				</button>
			{/each}
			{/snippet}
		</Wall>
	{:else}
		<div class="head">
			<h2>
				<span class="year">{year.year}</span>
				<span class="when">{ago(year.year) === 0
					? t('photos.thisYear')
					: t('photos.yearsAgo', { n: formatNumber(ago(year.year)) })}</span>
				{#if about(year.people)}<span class="who">{about(year.people)}</span>{/if}
			</h2>
		</div>
		<div class="shelf" class:tv={surface.isTv}>
			{#each shown as shot, i (shot.id)}
				<button
					class="tile"
					data-shot={shot.id}
					aria-label={formatDate(shot.taken_at)}
					style={shot.w && shot.h ? `aspect-ratio:${shot.w}/${shot.h}` : 'aspect-ratio:3/2'}
					onclick={() => (at = i)}
				>
					<img
						src={tileOf(shot.id, shot.turn)}
						alt=""
						loading="lazy"
						style:background-image={ground(shot)}
					/>
				</button>
			{/each}
		</div>
	{/if}
{/if}

{#snippet toTv(photo: Photo)}<PhotoToTv {photo} />{/snippet}

{#if at !== null && shown[at]}
	<PhotoViewer
		photo={shown[at] as never}
		hasPrev={at > 0}
		hasNext={at < shown.length - 1}
		neighbours={[shown[at - 1], shown[at + 1]].filter((p) => p !== undefined)}
		plays={recordingOf}
		actions={surface.isTv ? undefined : toTv}
		onclose={() => (at = null)}
		onprev={() => (at = Math.max(0, (at ?? 0) - 1))}
		onnext={() => (at = Math.min(shown.length - 1, (at ?? 0) + 1))}
	/>
{/if}

<style>
	/* A day is a handful of years: the picture, how long ago, and who it was
	   about — which is the part that makes somebody press it. */
	.card {
		display: grid;
		gap: 0.5rem;
		padding: 0;
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.picture {
		display: block;
		aspect-ratio: 3 / 2;
		border-radius: var(--card-radius, 12px);
		overflow: hidden;
		background: color-mix(in srgb, currentColor 8%, transparent);
	}
	.picture img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		background-size: cover;
		background-position: center;
		display: block;
	}
	.card:hover .picture {
		outline: var(--focus-ring);
		outline-offset: var(--focus-offset);
	}
	/* the ring the layer draws, around the whole card rather than around the
	   picture alone: what the remote is on is the year, and the caption is half
	   of what says which year it is */
	.card:focus-visible {
		outline: var(--focus-ring);
		outline-offset: var(--focus-offset);
		border-radius: var(--card-radius, 12px);
	}
	.said {
		display: grid;
		gap: 0.1rem;
		padding: 0 0.15rem;
	}
	.said .when {
		font-size: var(--fs-s);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.said .who {
		font-weight: 600;
	}
	.head {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		margin-bottom: 0.8rem;
	}
	/* The year is the heading, and how long ago it was is the part that is
	   actually read: "2005" is a number, "twenty-one years ago" is a memory. */
	h2 {
		display: flex;
		align-items: baseline;
		gap: 0.7rem;
		margin: 0 0 0.6rem;
		font-size: var(--fs-xl);
	}
	.year {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.when {
		color: var(--muted);
		font-weight: 400;
		font-size: var(--fs-m);
	}
	.how-many {
		margin-left: auto;
		color: var(--muted);
		font-weight: 400;
		font-size: var(--fs-m);
	}
	/* the same shelf the timeline draws, in rows that keep each picture's own
	   shape rather than cutting every one of them into a square */
	.shelf {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	/* Each picture keeps its own shape at one height, and the last row of a year
	   ends where it ends: stretching three photographs across the width to fill
	   a line is how a row of three becomes a wall. */
	.tile {
		flex: 0 0 auto;
		width: auto;
		max-width: 22rem;
		height: 9rem;
		padding: 0;
		border: none;
		border-radius: var(--radius-s, 8px);
		background: color-mix(in srgb, currentColor 8%, transparent);
		overflow: hidden;
		cursor: pointer;
	}
	.shelf.tv .tile {
		height: 7rem;
	}
	.tile img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		background-size: cover;
		background-position: center;
		display: block;
	}
	.tile:hover,
	.tile:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.quiet {
		color: var(--muted);
	}
</style>
