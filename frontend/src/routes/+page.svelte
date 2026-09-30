<script lang="ts">
	// What to watch or listen to now. Rows of the library, assembled by the
	// backend on the spot — the player keeps no catalogue, so nothing here can
	// be out of date.

	import Play from '$lib/screens/Play.svelte';
	import Sheet from '$lib/parts/Sheet.svelte';
	import Row from '$lib/parts/Row.svelte';
	import Hero from '$lib/parts/Hero.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { focusContent } from '$lib/tv/spatial.svelte';
	import { request, withLang } from '$lib/kit';
	import { me } from '$lib/opus';
	import { carryOn } from '$lib/ask/puton';
	import { preview } from '$lib/keep/preview.svelte';
	import { shelves } from '$lib/keep/shelves.svelte';
	import SurfacePicker from '$lib/parts/SurfacePicker.svelte';
	const devTools = import.meta.env.DEV;
	import { opened, playsAtOnce } from '$lib/say/pick';
	import { spoken } from '$lib/say/episode';
	import { surface } from '$lib/keep/surface.svelte';
	import { panel } from '$lib/keep/panel.svelte';
	import { i18n, t } from '$lib/i18n';
	import { goto } from '$app/navigation';
	import { SHELVES } from '$lib/keep/shelf.svelte';
	import type { Card, Row as RowType } from '$lib/keep/types';

	let rows = $state<RowType[]>([]);
	let loaded = $state(false);
	let problem = $state('');
	const over = panel();
	let playing = $state<Card | null>(null);

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

	function close() {
		if (over.close()) return;
		if (surface.isTv) setTimeout(focusContent, 0);
	}

	async function load() {
		problem = '';
		const said = await request<{ rows: RowType[] }>(withLang('/api/home'), {}, {
			failed: (detail) => (problem = detail)
		});
		if (said) rows = said.rows.map((row) => ({ ...row, cards: row.cards.map(spoken) }));
		loaded = true;
	}

	// A television has no page in front of its shelves: it opens on the first
	// shelf there is anything on.
	$effect(() => {
		if (!surface.isTv) return;
		const to = shelves.answered ? (SHELVES.find((s) => shelves.of(s).length) ?? 'movies') : '';
		if (to) void goto(`/${to}`, { replaceState: true });
	});

	$effect(() => {
		i18n.locale;
		if (!surface.isTv) load();
	});

	$effect(() => {
		void shelves.ask();
	});

	// The picture this screen stands in front of. Every section notes its shelf's
	// first card for the ground behind the page; home noted none, and home is the
	// one screen where the remote arrives in the MENU rather than on a poster —
	// so the first thing anybody sees of this surface was the only screen on it
	// with nothing behind the words. A wide picture is looked for before the
	// first card is taken: a poster is blurred into a colour, and home is the one
	// place with a whole library to find a backdrop in.
	$effect(() => {
		const cards = rows.flatMap((row) => row.cards);
		preview.front('home', cards.find((c) => c.backdrop) ?? cards[0]);
	});

	// What the whole library holds, for the panel to say before anything on the
	// screen has been pointed at. The photographs are the fifth kind — except
	// for a guest, who is trusted with the address and not with the family
	// album, and to whom a count of it is an inventory of a room they may not
	// enter.
	const rest = $derived({
		counts: shelves.everything(['movies', 'series', 'music', ...(me.guest ? [] : ['photos'])])
	});
</script>

{#if !surface.isTv}
<div class="screen">
<Hero {rest} />

<div class="walk">
{#if devTools}<SurfacePicker />{/if}

{#if problem || shelves.problem}
	<p class="muted">{t('home.libraryDown', { detail: problem || shelves.problem })}</p>
{:else if loaded && shelves.answered && !rows.length && !rest.counts.length}
	<p class="muted">{t('home.empty')}</p>
{/if}

{#if over.card}
	<Sheet
		card={over.card}
		onclose={close}
		onopen={over.stand}
		onplay={(c) => {
			playing = c;
			close();
		}}
	/>
{:else}
	{#each rows as row (row.key)}
		<Row
			{row}
			onpick={(c) => {
				if (c.kind === 'track') void carryOn(c);
				else if (playsAtOnce(row, c)) playing = c;
				else if (!opened(c)) choose(c);
			}}
		/>
	{/each}
{/if}
</div>
</div>
{/if}

{#if playing}
	<Play card={playing} onclose={() => (playing = null)} />
{/if}
