<script lang="ts">
	// One kind of thing out of the library, all of it. The home page shows rows
	// across every kind; this is what you get when you have stopped browsing and
	// gone looking for a film.

	import { i18n, t } from '$lib/i18n';
	import Hero from '$lib/parts/Hero.svelte';
	import Discover from '$lib/screens/Discover.svelte';
	import Radio from '$lib/screens/Radio.svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { hero } from '$lib/keep/hero.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { focusContent } from '$lib/tv/spatial.svelte';
	import Grid from '$lib/parts/Grid.svelte';
	import { Heading, narrow } from '$lib/kit';
	import Row from '$lib/parts/Row.svelte';
	import { carryOn } from '$lib/ask/puton';
	import { queue } from '$lib/keep/queue.svelte';
	import { initialOf, Letters, lettersOf, request, withLang } from '$lib/kit';
	import { me } from '$lib/opus';
	import { surface } from '$lib/keep/surface.svelte';
	import { watching } from '$lib/keep/watching.svelte';
	import { panel } from '$lib/keep/panel.svelte';
	import { SHELVES, shelf } from '$lib/keep/shelf.svelte';
	import WallHead from '$lib/tv/WallHead.svelte';
	import Info from '$lib/tv/Info.svelte';
	import Keyboard from '$lib/parts/Keyboard.svelte';
	import { shelves } from '$lib/keep/shelves.svelte';
	import { preview } from '$lib/keep/preview.svelte';
	import { discoverOf, pageOf, pagesUnder } from '$lib/say/ways';
	import Play from '$lib/screens/Play.svelte';
	import Sheet from '$lib/parts/Sheet.svelte';
	import { atItsArtist, opened, playsAtOnce } from '$lib/say/pick';
	import { want } from '$lib/ask/want';
	import type { Card, Row as RowType } from '$lib/keep/types';
	import type { QueueTrack } from '$lib/keep/queue.svelte';

	let { section }: { section: string } = $props();

	// A shelf is what is held; ?find= is where to look for more of it. Same
	// page, because "more films" belongs to the films and not to a screen of
	// its own.
	// any of these means the screen is about what there is more of rather than
	// about what is held — a person and a studio arrive without a `find` of
	// their own because they are asked for from a film's own screen
	const ASKS = ['find', 'person', 'company', 'genre', 'q'];
	const finding = $derived.by(() => {
		if (!ASKS.some((k) => page.url.searchParams.get(k))) return '';
		const find = page.url.searchParams.get('find') ?? 'who';
		if (find === 'all') return '';
		return find === 'discover' ? (discoverOf(section)[0] ?? '') : find;
	});

	let cards = $state<Card[]>([]);

	// the shelf's first picture is what the section stands in front of when the
	// menu passes it
	$effect(() => {
		preview.front(section, cards[0]);
	});
	// which shelf the cards on the screen belong to
	let held = $state('');
	let loaded = $state(false);
	let problem = $state('');
	const over = panel();
	let playing = $state<Card | null>(null);
	let favoriteTracks = $state<QueueTrack[]>([]);
	let rows = $state<RowType[]>([]);
	let favoriteTurn = 0;

	const choose = over.open;

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

	/** Where to look for more of this shelf. The letters are one of them: the
	 *  keyboard stands where the answers will be rather than in the panel, which
	 *  has room for a sentence and not for an alphabet. */
	function look(which: string) {
		if (which === 'spell' && walled) {
			spelling = true;
			return;
		}
		goto(`/${section}?find=${which === 'spell' ? 'search' : which}`, { keepFocus: false });
	}

	function close() {
		if (over.close()) return;
		if (surface.isTv) setTimeout(focusContent, 0);
	}

	// The letters, when the wall is in an order letters mean anything in: down
	// the edge where a finger slides. Ten feet away there is no strip at all —
	// a column of thirty letters beside the wall reads as a form standing in
	// front of the pictures; holding the arrow down is how a long wall is
	// crossed there.
	const alphabetical = $derived(
		!finding && !over.card && shelf.of(section).order === 'title' && cards.length > 12
	);
	const letters = $derived(alphabetical ? lettersOf(cards.map((c) => c.title)) : []);
	function firstOf(letter: string): HTMLElement | null {
		const first = cards.find((c) => initialOf(c.title) === letter);
		return first
			? document.querySelector<HTMLElement>(`[data-perch="${first.kind}:${first.id}"]`)
			: null;
	}
	function jump(letter: string) {
		firstOf(letter)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}
	// a shelf section opens on rows and keeps its whole wall a page below, on
	// every surface; walled is what only a television does on top of that
	const rowed = $derived((SHELVES as readonly string[]).includes(section));
	const walled = $derived(surface.isTv && rowed);
	const onPage = $derived(rowed ? pageOf(page.url.searchParams) : '');

	// the discovery questions are one page in the menu, and the pills in the
	// head are how you move between them once you are on it
	const discovering = $derived(walled && discoverOf(section).includes(finding));
	// Searching is the last of them, and it is asked in a window over the page:
	// the letters are not a place anybody goes, they are how a question is put.
	const asking = $derived(walled && (discovering || finding === 'search'));
	const headWays = $derived(
		asking
			? [...discoverOf(section), 'spell']
			: surface.isTv || !narrow.current
				? []
				: pagesUnder(section)
	);
	let spelling = $state(false);
	let typed = $state('');
	function ask() {
		const query = typed.trim();
		if (!query) return;
		spelling = false;
		goto(`/${section}?find=search&q=${encodeURIComponent(query)}`);
	}

	// A section opens on rows — what this person was in the middle of and, for
	// music, what they keep going back to and what just came in — and the whole
	// wall is a page of its own below them.
	let rowTurn = 0;
	let rowsIn = $state(false);
	$effect(() => {
		const asked = rowed ? section : '';
		watching.profile?.key;
		i18n.locale;
		const turn = ++rowTurn;
		rows = [];
		rowsIn = false;
		if (!asked) return;
		void request<{ rows: RowType[] }>(withLang(`/api/rows/${asked}`), {}, { failed: () => {} }).then(
			(found) => {
				if (turn !== rowTurn) return;
				rows = found?.rows ?? [];
				rowsIn = true;
			}
		);
	});

	// What the section's own link opens: what this person is in the middle of.
	// Somebody in the middle of nothing gets the whole shelf instead, because a
	// page that opens empty is a page that has to be walked out of.
	const carried = $derived(rows.filter((row) => row.key !== 'just_in' && row.cards.length));
	const carrying = $derived(carried.length > 0 || favoriteTracks.length > 0);
	const whole = $derived(onPage === 'all' || (onPage === '' && rowsIn && !carrying));
	const lettered = $derived(alphabetical && !surface.isTv && (!rowed || whole));

	function pickInRow(c: Card, row: RowType) {
		if (c.kind === 'track') void carryOn(c);
		else if (playsAtOnce(row, c)) playing = c;
		else if (!opened(c)) choose(atItsArtist(c));
	}

	let loads = 0;

	async function load() {
		// The shelf is not taken down while it is being asked for again. Changing
		// how it is arranged, or what language it answers in, empties the screen
		// and fills it back a third of a second later — which from a sofa is the
		// shelf falling over rather than being tidied. Only arriving at a
		// different shelf clears it, and that starts empty anyway.
		if (held !== section) {
			cards = [];
			loaded = false;
		}
		held = section;
		const chosen = shelf.of(section);
		const turn = ++loads;
		let why = '';
		const said = await request<Card[]>(`/api/library/${section}?order=${chosen.order}:${chosen.way}`, {}, {
			failed: (detail) => (why = detail)
		});
		// only the last question asked is the shelf on the screen
		if (turn !== loads) return;
		cards = said ?? cards;
		problem = why;
		loaded = true;
	}

	// the shelf's totals, the same numbers the menu says about it while the
	// remote is only passing
	$effect(() => {
		void shelves.ask();
	});

	// This is a person's shelf, never a television's household shelf. The
	// Player adds current catalogue details to each saved id before it reaches
	// here, so an old favourite cannot become a stale title in the web UI.
	$effect(() => {
		const person = section === 'music' ? watching.person : '';
		const turn = ++favoriteTurn;
		favoriteTracks = [];
		if (!person) return;
		void request<{ tracks: QueueTrack[] }>('/api/music/favorites').then((found) => {
			if (turn === favoriteTurn && found) favoriteTracks = found.tracks;
		});
	});

	// The counts stay in the head whatever the ring is on: counts that come and
	// go with the ring move the shelf under them by a line at every crossing.
	// Radio is a shelf of this section like any other: how much is on it is
	// said in the same head.
	const rest = $derived({ counts: shelves.of(finding === 'radio' ? 'radio' : section) });

	// ?open=artist:12 — the house sent the television to one thing on this
	// shelf. Opened once and taken out of the address, so closing it stays closed.
	$effect(() => {
		const asked = page.url.searchParams.get('open');
		if (!asked || !loaded) return;
		const [kind, id] = asked.split(':');
		const card = cards.find((c) => c.kind === kind && String(c.id) === id);
		void goto(page.url.pathname, { replaceState: true, keepFocus: true, noScroll: true });
		if (card) choose(card);
	});

	$effect(() => {
		section;
		const chosen = shelf.of(section);
		chosen.order;
		chosen.way;
		// the catalogue answers in the frame's language, so switching it is a
		// reason to ask again
		i18n.locale;
		load();
	});
</script>

<!-- Which shelf you are standing at, and how much is on it. The frame's own
     nav says it too, but a person looking from a sofa reads the thing they came
     for before they read the menu they came through. -->
<!-- The head stays and the shelf walks under nothing. It used to scroll under
     the head, and the head is a fade rather than a panel — so the description
     of the film the ring was on was written across a row of posters, and
     neither could be read. -->
<div class="screen">
<Hero {rest} {section} ways={headWays} on={finding === 'search' ? 'spell' : finding || onPage} onway={look} />

<div class="walk">
{#if problem}
	<p class="muted">{t('home.libraryDown', { detail: problem })}</p>
{/if}

{#if loaded}
	{#if finding === 'radio'}
		<Radio />
	{:else if finding}
		<Discover {section} find={finding} />
	{:else if over.card}
		<!-- what was chosen takes the shelf's place: its seasons or its records,
		     under the panel that is now about it -->
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
	{:else}
		<!-- No heading: the panel above already names this shelf and counts it,
		     and a second copy of the same sentence a line below the first is not
		     structure, it is the same thing said twice. -->
		<section class="shelf" class:tv={surface.isTv}>
			{#if !rowed}
				{@render favorites()}
				<Grid {cards} onpick={(c) => !opened(c) && choose(c)} />
			{:else if whole}
				<WallHead {section} />
				<Grid {cards} onpick={(c) => !opened(c) && choose(c)} />
			{:else}
				{#each carried as row (row.key)}
					<Row {row} onpick={(c) => pickInRow(c, row)} />
				{/each}
				{@render favorites()}
			{/if}
		</section>
		{#if lettered}
			<Letters {letters} onjump={jump} />
		{/if}
	{/if}
{/if}
</div>
</div>

<Info bind:open={spelling} title={t('find.spell')} remote={false} side>
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
</Info>

{#snippet favorites()}
	{#if section === 'music' && favoriteTracks.length}
		<Heading label={t('music.favorites')} count={favoriteTracks.length} />
		<ol class="favorites">
			{#each favoriteTracks as track, index (track.id)}
				<li><button onclick={() => queue.play(favoriteTracks, index)}>
					<span>{track.title}</span><small>{track.artist} · {track.album}</small>
				</button></li>
			{/each}
		</ol>
	{/if}
{/snippet}

{#if playing}
	<Play card={playing} onclose={() => (playing = null)} />
{/if}

<style>
	.favorites { list-style: none; margin: 0 0 1.5rem; padding: 0; max-width: 42rem; }
	.favorites button { display: grid; gap: 0.1rem; width: 100%; padding: 0.55rem 0.7rem; border: 0; border-radius: 8px; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; }
	.favorites button:hover, .favorites button:focus-visible { background: color-mix(in srgb, var(--accent) 14%, transparent); }
	.favorites small { color: var(--muted); }
	/* the ruler stands before the wall, and the wall takes the rest */
</style>
