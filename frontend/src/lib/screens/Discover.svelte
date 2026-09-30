<script lang="ts">
	// What exists in the world. Nothing here is owned yet, so the only thing a
	// card offers is to want it — after which it stops being this screen's
	// business and becomes a download in the Library's queue.

	import { art } from '$lib/ask/art';
	import Row from '$lib/parts/Row.svelte';
	import Grid from '$lib/parts/Grid.svelte';
	import Play from '$lib/screens/Play.svelte';
	import Sheet from '$lib/parts/Sheet.svelte';
	import { Heading } from '$lib/kit';
	import Keyboard from '$lib/parts/Keyboard.svelte';
	import Who from '$lib/parts/Who.svelte';
	import { hero } from '$lib/keep/hero.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { panel } from '$lib/keep/panel.svelte';
	import { focusContent } from '$lib/tv/spatial.svelte';
	import { forget, keep, recall, request } from '$lib/kit';
	import { atItsArtist, opened } from '$lib/say/pick';
	import { want } from '$lib/ask/want';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { formatNumber, t } from '$lib/i18n';
	import type { Card, Row as RowType, Somebody } from '$lib/keep/types';
	import { winners } from '$lib/keep/awards';
	import { STANCES, readStances, servicesOf, sift, writtenStances, type Stances } from '$lib/keep/streaming';
	import { nav } from '$lib/tvui/nav.svelte';
	import Portrait from '$lib/tvui/Portrait.svelte';
	import Choose, { type Option } from '$lib/tvui/Choose.svelte';

	let { section = 'movies', find = 'trending' }: { section?: string; find?: string } =
		$props();

	// the shelf this was asked from, in the word TMDB uses for it
	const kind = $derived(section === 'series' ? 'tv' : 'movie');

	let rows = $state<RowType[]>([]);
	let found = $state<Card[] | null>(null);
	// a list the house draws up rather than an answer to something typed
	let listed = $state(false);
	let asked = $state('');
	// what to call the wall of posters that came back
	let title = $state('');
	// the ways in that are lists of names rather than walls of posters
	let names = $state<
		{ label: string; to: string; note?: string; image?: string | null }[] | null
	>(null);
	// the shelf this was opened from, which is where every answer goes back to
	const here = $derived(page.url.pathname);
	let awarded = $state<{ awards: string[]; cards: Card[] } | null>(null);
	let awardStances = $state<Stances>({ only: [], without: [] });
	const shelved = $derived(awarded ? winners(awarded.cards, awardStances) : []);

	let stances = $state<Stances>({ only: [], without: [] });
	$effect(() => {
		stances = readStances(recall(STANCES));
	});

	function keepStances() {
		const written = writtenStances(stances);
		if (written) keep(STANCES, written);
		else forget(STANCES);
	}

	const winnerServices = $derived(servicesOf(shelved));
	const foundServices = $derived(found ? servicesOf(found) : []);
	const winnersShown = $derived(sift(shelved, stances, winnerServices));
	const foundShown = $derived(found ? sift(found, stances, foundServices) : []);

	/** Genres, the people in the house, the studios behind it — each of them a
	 *  list of names that opens a wall of posters, and music, which is already
	 *  one. An answer is taken only while its question is still the one on the
	 *  screen. */
	async function asking(which: string, question: string) {
		const current = () => asked === question;
		names = null;
		found = null;
		awarded = null;
		if (which === 'trending' || which === 'offered') {
			const answer = await request<{ rows: RowType[] }>(
				which === 'offered' ? '/api/explore/music' : `/api/explore?type=${kind}`
			);
			if (!current()) return;
			rows = answer?.rows ?? [];
			title = '';
			if (surface.isTv) setTimeout(focusContent, 0);
			return;
		}
		if (which === 'releases' || which === 'similar') {
			const answer = await request<Card[]>(`/api/explore/music/${which}`);
			if (!current()) return;
			title = t(`find.${which}`);
			found = answer ?? [];
			listed = true;
			if (surface.isTv) setTimeout(focusContent, 0);
			return;
		}
		if (which === 'awards') {
			const answer = await request<{ awards: string[]; cards: Card[] }>(
				`/api/explore/awarded?type=${kind}`
			);
			if (!current()) return;
			awarded = answer;
			awardStances = { only: [], without: [] };
			if (surface.isTv) setTimeout(focusContent, 0);
			return;
		}
		title = t(`find.${which}` as never);
		if (which === 'genres') {
			const answer = await request<{ name: string; ids: Record<string, number> }[]>(
				`/api/explore/genres?type=${kind}`
			);
			if (!current()) return;
			names = (answer ?? []).map((g) => ({
				label: g.name,
				to:
					`${here}?name=${encodeURIComponent(g.name)}&genre=` +
					encodeURIComponent(
						Object.entries(g.ids)
							.map(([k, v]) => `${k}=${v}`)
							.join('&')
					)
			}));
		} else if (which === 'actors') {
			const answer = await request<
				{ id: number; name: string; held: number; profile_url: string | null }[]
			>(`/api/explore/people?type=${kind}`);
			if (!current()) return;
			names = (answer ?? []).map((p) => ({
				label: p.name,
				to: `${here}?person=${p.id}`,
				image: p.profile_url,
				note: formatNumber(p.held)
			}));
		} else if (which === 'studios') {
			const answer = await request<{ id: number; name: string; held: number }[]>(
				`/api/explore/studios?type=${kind}`
			);
			if (!current()) return;
			names = (answer ?? []).map((c) => ({
				label: c.name,
				to: `${here}?company=${c.id}`,
				note: formatNumber(c.held)
			}));
		}
		if (surface.isTv) setTimeout(focusContent, 0);
	}
	// who was asked about, when the question was a person or a studio
	let who = $state<Somebody | null>(null);
	const over = panel();

	const open = over.open;
	const choose = (c: Card) => open(atItsArtist(c));

	$effect(() =>
		onBack(
			() => {
				if (!over.card) return false;
				close();
				return true;
			},
			() => over.card !== null
		)
	);

	function close() {
		if (over.close()) return;
		if (surface.isTv) setTimeout(focusContent, 0);
	}
	let playing = $state<Card | null>(null);

	// The question is asked in the rail, with the letters that open beside it,
	// and arrives here as the address. A text box in the middle of the screen
	// was a place the remote could reach and then do nothing with.
	//
	// A face on a film's billing asks a different question at the same screen:
	// everything else that person is in. Same answer, same wall of posters.
	$effect(() => {
		const q = page.url.searchParams.get('q')?.trim() ?? '';
		const person = page.url.searchParams.get('person')?.trim() ?? '';
		const made = page.url.searchParams.get('company')?.trim() ?? '';
		const genre = page.url.searchParams.get('genre')?.trim() ?? '';
		const question = person
			? `person:${person}`
			: made
				? `company:${made}`
				: genre
					? `genre:${genre}`
					: find === 'search'
						? `q:${q}`
						: `find:${find}:${section}`;
		if (question === asked) return;
		asked = question;
		who = null;
		names = null;
		awarded = null;
		if (!question) {
			found = null;
			title = '';
			return;
		}
		const current = () => asked === question;
		const named = (path: string) =>
			request<Somebody & { cards: Card[] }>(path).then((r) => {
				if (!current()) return null;
				title = r?.name ?? '';
				who = r ? { ...r } : null;
				return r?.cards ?? null;
			});
		if (!person && !made && !genre && find !== 'search') {
			void asking(find, question);
			return;
		}
		const answer = person
			? named(`/api/explore/person/${person}`)
			: genre
				? request<Card[]>(`/api/explore/genre?${genre}`).then((hits) => {
						if (current()) title = page.url.searchParams.get('name') ?? t('explore.view.genres');
						return hits;
					})
			: made
				? named(`/api/explore/company/${made}`)
				: request<Card[]>(
						section === 'music'
							? `/api/explore/music/search?q=${encodeURIComponent(q)}`
							: `/api/explore/search?type=${kind}&q=${encodeURIComponent(q)}`
					).then((hits) => {
						if (current()) title = t('explore.found', { query: q });
						return hits;
					});
		void answer.then((hits) => {
			if (!current()) return;
			found = hits;
			listed = false;
			if (surface.isTv) setTimeout(focusContent, 0);
		});
	});

	let typed = $state('');

	function ask() {
		const query = typed.trim();
		if (query) goto(`/${section}?find=search&q=${encodeURIComponent(query)}`);
	}
	// A result is a place you went, not a strip inside the shelf. On a
	// television discovery is itself one of the section's pages, beside the menu;
	// what takes the screen there is a person, a studio or a genre asked for
	// from a film.
	const deep = $derived(['person', 'company', 'genre'].some((k) => page.url.searchParams.get(k)));
	$effect(() => (!surface.isTv || deep ? nav.takes() : undefined));

</script>

<!-- The letters, where the answers will be. Asking to spell something out is
     not an answer yet, so this stands until there is a word to look for; typing
     one replaces it with what was found. -->
{#snippet streaming(offered: Option[])}
	{#if offered.length}
		<Choose
			as="row"
			options={offered}
			bind:chosen={stances.only}
			bind:refused={stances.without}
			cycle
			many
			onpick={keepStances}
		/>
	{/if}
{/snippet}

{#if find === 'search' && !page.url.searchParams.get('q')}
	<section class="spell">
		<Heading label={t('find.spell')} />
		<Keyboard
			value={typed}
			hint={t(
				section === 'music'
					? 'explore.search.music'
					: section === 'series'
						? 'explore.search.series'
						: 'explore.search.movies'
			)}
			onchange={(next) => (typed = next)}
			onsubmit={ask}
		/>
	</section>
{:else if over.card}
	<Sheet
		card={over.card}
		onclose={close}
		onopen={over.stand}
		onplay={(c) => {
			playing = c;
			close();
		}}
		onwant={(c, seasons, only) => {
			close();
			want(c, seasons, only);
		}}
	/>
{:else if names}
	<!-- a list of names is not a wall of posters: each one opens one -->
	<section>
		<Heading label={title} count={names.length} />
		<!-- people have faces; a genre or a studio is a word -->
		<div class="names" class:faces={names.some((n) => n.image !== undefined)}>
			{#each names as one (one.to)}
				<button onclick={() => goto(one.to)}>
					{#if one.image !== undefined}
						<Portrait
							rung="face"
							src={one.image ? art(one.image, 320) : undefined}
							name={one.label}
						/>
					{/if}
					<span class="label">{one.label}</span>
					{#if one.note}<span class="note">{one.note}</span>{/if}
				</button>
			{/each}
		</div>
	</section>
{:else if awarded}
	<section>
		<Heading label={t('find.awards')} count={winnersShown.length} />
		<div class="filters">
			<Choose
				as="row"
				options={awarded.awards.map((key) => ({ key, label: t(`award.${key}` as never), image: `/awards/${key}.svg` }))}
				bind:chosen={awardStances.only}
				bind:refused={awardStances.without}
				cycle
				many
			/>
			{@render streaming(winnerServices)}
		</div>
		<Grid cards={winnersShown} onpick={(c) => !opened(c) && choose(c)} />
	</section>
{:else if found}
	<!-- the same shape a shelf has: a small label over what is under it -->
	<section>
		{#if who}
			<Who
				name={who.name}
				about={who.about}
				image={art(who.image, 320)}
				born={who.born}
				died={who.died}
				place={who.from}
			/>
		{/if}
		<Heading label={who ? t('explore.work') : title} count={foundShown.length} />
		{#if foundServices.length}
			<div class="filters">{@render streaming(foundServices)}</div>
		{/if}
		{#if foundShown.length}
			<Grid cards={foundShown} onpick={(c) => !opened(c) && choose(c)} />
		{:else}
			<p class="muted">{listed ? t('explore.empty') : t('explore.nothing', { query: title })}</p>
		{/if}
	</section>
{:else}
	{#each rows as row (row.key)}
		<Row {row} onpick={(c) => !opened(c) && choose(c)} />
	{/each}
{/if}

{#if playing}
	<Play card={playing} onclose={() => (playing = null)} />
{/if}

<style>
	.filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1.2rem;
		margin: 0 0 1.1rem;
	}
	.names {
		display: grid;
		/* NAME in cells.ts: the same list the places draw, the same width — it
		   was 13rem here and 15rem there, two numbers for one thing */
		grid-template-columns: repeat(auto-fill, minmax(min(240px, 100%), 1fr));
		gap: 0.4rem;
	}
	/* a wall of faces reads at a glance where a column of names does not */
	.names.faces {
		/* FACE in cells.ts. Eight declared columns drew a person at 72px here
		   and 110 in the photographs — three sizes for one kind of thing; the
		   count now falls out of the same cell the photographs use */
		grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
		gap: 1rem 0.8rem;
	}
	.names.faces button {
		flex-direction: column;
		align-items: center;
		justify-content: flex-start;
		gap: 0.4rem;
		padding: 0.4rem 0.2rem;
		border: none;
		text-align: center;
	}
	.names.faces .label {
		font-size: var(--fs-s);
		white-space: normal;
		line-height: 1.25;
	}
	.names.faces .note {
		display: none;
	}
	.names button {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.6rem;
		padding: 0.5rem 0.8rem;
		border: 1px solid color-mix(in srgb, var(--border) 55%, transparent);
		border-radius: var(--radius-m);
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.names button:focus-visible {
		outline: none;
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 20%, transparent);
	}
	.names .label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.names .note {
		color: var(--muted);
		font-size: 0.85em;
	}


</style>
