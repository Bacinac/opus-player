<script lang="ts">
	// The household's photographs, which are the one kind in the library with no
	// releases, no episodes and no runtime — a date, a place and who is in them.
	// So they get a screen of their own rather than a shelf bent to fit: a shelf
	// of films sorted by title says nothing about a Tuesday in 2019.
	//
	// Three ways in, and they are not three views of one thing. Time is the
	// shelf in the order it happened. People is who is on it, each one gathered
	// across the years. Places is where the house has been.

	import { untrack } from 'svelte';
	import { formatNumber, i18n, t } from '$lib/i18n';
	import { narrow, request } from '$lib/kit';
	import { cropOf, me, MediaHead, morphOf, previewOf } from '$lib/opus';
	import PhotoQuery from '$lib/opus/PhotoQuery.svelte';
	import PhotoTimeline from '$lib/opus/PhotoTimeline.svelte';
	import PhotoToTv from '$lib/parts/PhotoToTv.svelte';
	import type { Photo } from '$lib/keep/tvPhoto.svelte';
	import Keyboard from '$lib/parts/Keyboard.svelte';
	import { askRecordings, recordingOf } from '$lib/ask/ability';
	import PlaceMap from '$lib/parts/PlaceMap.svelte';
	import Ledger from '$lib/tvui/Ledger.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { focusContent, focusFirst } from '$lib/tv/spatial.svelte';
	import { count, fact } from '$lib/say/count';
	import * as photos from '$lib/ask/photos';
	import { played } from '$lib/keep/played.svelte';
	import { give, shared } from '$lib/keep/give.svelte';
	import { page } from '$app/state';
	import { afterNavigate } from '$app/navigation';
	import { nav } from '$lib/tvui/nav.svelte';
	import { preview } from '$lib/keep/preview.svelte';
	import Wall from '$lib/tvui/Wall.svelte';
	import { FACE, DESK_FACE, NAME } from '$lib/tvui/cells';
	import { waysOf } from '$lib/say/ways';
	import { onBack } from '$lib/keep/back.svelte';
	import Hero from '$lib/parts/Hero.svelte';
	import Portrait from '$lib/tvui/Portrait.svelte';
	import Today from '$lib/parts/Today.svelte';
	import Guess from './Guess.svelte';

	type Way = 'today' | 'time' | 'people' | 'places' | 'guess' | 'spell';

	let way = $state<Way>('today');
	let faces = $state<photos.Face[]>([]);
	let wheres = $state<photos.Where[]>([]);
	let here = $state<string | null>(null);
	/** the country a television has gone into, by its code */
	let country = $state<string | null>(null);
	let atCountry = $state<string | number | null>(null);
	let atPlace = $state<string | number | null>(null);
	let who = $state<photos.Face | null>(null);
	// where the shelf was opened from, so going back goes back rather than
	// somewhere sensible-looking. Whoever was chosen stays chosen, because a
	// list that forgets where you were in it is a list you have to search again.
	let from = $state<Way>('today');
	let chosen = $state<number | null>(null);
	let typed = $state('');
	/** what the shelf was last asked for, which the letters stay filled with */
	let searched = $state('');

	// last, and only where somebody proved who they are. A television came
	// through the household door and is nobody, so there is nothing here for it
	// — not hidden, absent.
	let months = $state<photos.Month[]>([]);
	let held = $state(0);

	type Country = {
		code: string;
		name: string;
		places: photos.Where[];
		photographs: number;
		cover: photos.Where | undefined;
		first: string;
		last: string;
	};

	/** A television reads the places a country at a time: forty towns in one
	 *  list is a list nobody walks, and the country is the first thing anybody
	 *  remembers about where a picture was taken. */
	const countries = $derived.by((): Country[] => {
		const names = new Intl.DisplayNames([i18n.locale], { type: 'region' });
		const nameOf = (code: string) => {
			if (!code) return t('photos.noCountry');
			try {
				return names.of(code) ?? code;
			} catch {
				return code;
			}
		};
		const by = new Map<string, photos.Where[]>();
		for (const where of wheres) {
			const code = (where.country ?? '').toUpperCase();
			const list = by.get(code);
			if (list) list.push(where);
			else by.set(code, [where]);
		}
		return [...by]
			.map(([code, places]) => ({
				code,
				name: nameOf(code),
				places,
				photographs: places.reduce((n, p) => n + p.photographs, 0),
				cover: places.find((p) => p.cover),
				first: places.map((p) => p.first ?? '').filter(Boolean).sort()[0] ?? '',
				last: places.map((p) => p.last ?? '').filter(Boolean).sort().at(-1) ?? ''
			}))
			.sort((a, b) => b.photographs - a.photographs);
	});
	const inCountry = $derived(countries.find((c) => c.code === country) ?? null);
	const opened = $derived(here ? (wheres.find((w) => w.place === here) ?? null) : null);

	/** the years something ran between, as a place or a country is remembered */
	const span = (first?: string | null, last?: string | null) => {
		const a = first?.slice(0, 4) ?? '';
		const b = last?.slice(0, 4) ?? '';
		return a && b && a !== b ? `${a}–${b}` : a || b;
	};

	/** What this shelf is, in the terms every other shelf in the player states
	 *  itself: how much of it there is, painted its own kind's colour. */
	const facts = $derived.by(() => {
		const counts = [];
		if (held) counts.push(count(held, 'photos'));
		if (faces.length) counts.push(count(faces.length, 'people'));
		if (wheres.length) counts.push(count(wheres.length, 'places'));
		const years = [...new Set(months.map((m) => m.month.slice(0, 4)))].sort();
		if (years.length > 1) counts.push(fact(`${years[0]}–${years[years.length - 1]}`, 'years'));
		return counts;
	});

	// the views ARE the ways, in the words the ways speak, and the list is the
	// one say/ways.ts keeps for every section — including which of them a person
	// gets and a television does not
	const waysHere = waysOf('photos');

	// The width the circles are actually drawn at, which is the width the
	// library is asked to draw them at, and the width the still beside it is cut
	// at, so a circle that starts moving does not also go soft.
	const TILE_FACE = 256;

	/** Whose circle is being looked at, and so the only one that moves. */
	let lively = $state<number | null>(null);

	// Arriving from the phone's share sheet. The worker held what was shared
	// and sent the person here; the sending itself happens now, from the page,
	// so it goes the way the button goes and can be watched while it does.
	let took = false;
	$effect(() => {
		if (took) return;
		const said = page.url.searchParams;
		if (said.has('shared')) {
			took = true;
			void (async () => {
				const files = await shared();
				if (files.length) await give.put(files);
			})();
		} else if (said.has('given')) {
			// the Android shell's door: it holds the file and the cookie, so it
			// sends them itself and arrives here with only the tally
			took = true;
			give.sent = Number(said.get('given')) || 0;
			give.known = Number(said.get('known')) || 0;
			give.failed = Number(said.get('failed')) || 0;
			give.total = give.sent + give.known + give.failed;
		}
	});

	// The section's own picture behind the whole page, like every other section —
	// and a different one every time it is opened. It was the newest photograph,
	// which is the same picture behind the same screen every evening; a family
	// album is worth a ground that reminds you what is in it.
	//
	// Weighted by how much each month holds, or the ground would mostly be
	// whichever month somebody happened to import fifty pictures from.
	$effect(() => {
		const buckets = months;
		if (!buckets.length) return;
		void (async () => {
			const all = buckets.reduce((n, b) => n + (b.count ?? 0), 0);
			let at = Math.random() * all;
			const when = buckets.find((b) => (at -= b.count ?? 0) <= 0) ?? buckets[0];
			const said = await request<{ photos?: { id: string; turn: number }[] }>(
				`/api/photos/timeline?month=${when.month}&limit=60`
			);
			const list = said?.photos ?? [];
			const one = list[Math.floor(Math.random() * list.length)];
			if (one) {
				preview.front('photos', {
					kind: 'photo',
					backdrop: previewOf(one.id, one.turn)
				} as never);
			}
		})();
	});

	$effect(() => {
		untrack(() => survey());
	});

	/** The three small answers the header is made of, asked once. They also
	 *  make People and Places open without waiting, which is what they cost. */
	async function survey() {
		const [b, f, w] = await Promise.all([photos.months(), photos.faces(), photos.wheres()]);
		months = b.months ?? [];
		held = b.total ?? 0;
		// Somebody with no face gathered to them is a name, not a person to open:
		// the library keeps them because a name is still somewhere to put a group
		// tomorrow, but a grid of faces has nothing to show for them and a shelf
		// behind them is empty.
		faces = f.filter((one) => (one.faces ?? 0) > 0);
		wheres = w;
	}


	// A way pressed in the MENU is a press on another screen: it arrives here as
	// an address, the way every other section's ways do, and only if it is one
	// this section offers. Taken on every arrival, not on every change of
	// address: the screen never writes the address, so a person opened from
	// People is still at ?find=people, and pressing People again is how you get
	// back to the faces.
	afterNavigate(() => {
		// on a television the section's own link is the section's first view
		const asked = page.url.searchParams.get('find') ?? (surface.isTv ? waysHere[0] : '');
		if (asked && waysHere.includes(asked)) pick(asked as Way);
	});

	function pick(k: Way) {
		who = null;
		here = null;
		country = null;
		from = 'time';
		searched = '';
		way = k;
		// a remote has nowhere to be until something on the page takes it
		if (surface.isTv) setTimeout(focusContent, 0);
	}

	function open(where: string) {
		from = 'places';
		here = where;
		who = null;
		way = 'time';
		if (surface.isTv) setTimeout(focusContent, 0);
	}

	function openPerson(face: photos.Face) {
		from = 'people';
		chosen = face.id;
		who = face;
		here = null;
		way = 'time';
		// The face the ring was on unmounts with the grid, and focus falls to
		// the document body — where every arrow is dead until one of them
		// happens to be rescued by a fallback. From the sofa that reads as "I
		// picked her and the remote stopped working." It lands in the shelf that
		// just opened instead, which is also the answer to "where am I". On a
		// television no way out is drawn: the remote's own BACK key is it.
		//
		// After the grid has actually gone, not while it is still standing: the
		// lander stands down the moment anything else holds the remote, and
		// called from here the thing still holding it is the face being left —
		// it would stand down, the face would unmount, and the ring would fall to
		// the document all the same.
		if (surface.isTv) setTimeout(focusContent, 0);
	}

	function clear() {
		const was = here;
		who = null;
		here = null;
		way = from;
		// same rule on the way back: what held the ring unmounts under it
		if (surface.isTv && was !== null)
			setTimeout(() => focusFirst(`.ledger .line[data-key="${CSS.escape(was)}"]`), 60);
		else if (surface.isTv) setTimeout(() => focusFirst('.head .ways button.on, .head .ways button'), 60);
	}

	function enter(code: string) {
		country = code;
		atPlace = null;
		setTimeout(() => focusFirst('.ledger .line'), 60);
	}

	function leaveCountry() {
		const was = country ?? '';
		country = null;
		setTimeout(() => focusFirst(`.ledger .line[data-key="${CSS.escape(was)}"]`), 60);
	}

	/** Bring the one who was chosen back into view, since a list of a hundred
	 *  and twenty-three is a list you would otherwise have to find her in. */
	function mark(node: HTMLElement, id: number) {
		if (chosen === id) node.scrollIntoView({ block: 'center' });
		return {};
	}

	// one person, or one place, is a page about them rather than a view of the
	// shelf — the three tabs are the shelf, and these are what opens off it
	$effect(() => (who || here || country !== null ? nav.takes() : undefined));

	/** the photograph open over the shelf, if one is */
	let viewing = $state<number | null>(null);

	// and a page you can open is a page you can leave. It had no rung, so BACK
	// fell past it to the frame's ladder, which pops a path segment — and the
	// person stayed on the screen while the address went somewhere else.
	$effect(() =>
		onBack(
			() => {
				if (viewing !== null) {
					viewing = null;
					return true;
				}
				if (who || here) {
					clear();
					return true;
				}
				if (searched) {
					searched = '';
					if (surface.isTv) setTimeout(focusContent, 0);
					return true;
				}
				if (country === null) return false;
				leaveCountry();
				return true;
			},
			() => viewing !== null || !!(who || here) || !!searched || country !== null
		)
	);


	askRecordings();
</script>

<!-- The same head every other section wears, with the three views as its ways.
     This screen used to draw a PageHead of its own — its own title, its own
     private strip of tabs — which is what "the photo page is out of step" was:
     one section dressed differently from the four beside it. -->
<!-- while a round is running the section steps out of the way: its title,
     its counts and its row of ways are how somebody ARRIVED at the game,
     and on a phone they were the top third of the screen with a clock going -->
<div class="screen">
{#if surface.isTv && inCountry && !here}
	<!-- a country is a page about one thing, and wears that head -->
	<div class="named">
		<MediaHead
			title={inCountry.name}
			amount={formatNumber(inCountry.places.length)}
			subtitle={[count(inCountry.photographs, 'photos').text, span(inCountry.first, inCountry.last)]
				.filter(Boolean)
				.join(' · ')}
		/>
	</div>
{:else if !who && !here && !played.playing}
	<Hero
		rest={{ counts: facts }}
		ways={surface.isTv || !narrow.current ? [] : waysHere}
		onway={(w) => pick(w as Way)}
		on={way}
		tells={false}
	/>
{/if}

<!-- What is walked has its own box, beginning where the head ends. There is no
     description in this section — a photograph's caption is its own — so the
     counts are the line the wall must not go under. -->
<div class="walk">
<!-- The doing moved beside the person's name, where it follows them; what
     became of it stays here, because here is where the photographs land. -->
{#if give.running || give.total}
	<div class="give">
		{#if give.running}
			<span class="told">{t('photos.giving', { name: give.now })}</span>
		{:else}
			<span class="told">
				{t('photos.gave', {
					sent: formatNumber(give.sent),
					known: formatNumber(give.known),
					failed: formatNumber(give.failed)
				})}
			</span>
			{#if give.trouble}<span class="trouble">{give.trouble}</span>{/if}
		{/if}
	</div>
{/if}

{#if way === 'today'}
	<Today />
{:else if way === 'spell' && !searched}
	<Keyboard
		value={typed}
		hint={t('photos.search.hint')}
		onchange={(next) => (typed = next)}
		onsubmit={() => {
			searched = typed.trim();
			if (surface.isTv) setTimeout(focusContent, 0);
		}}
	/>
{:else if way === 'guess'}
	<Guess />
{:else if way === 'people' && !who}
	<Wall cell={surface.isTv ? FACE.cell : DESK_FACE.cell} gap={surface.isTv ? FACE.gap : DESK_FACE.gap}>
		{#snippet children(_across)}
		{#each faces as face (face.id)}
			<button
				class="face"
				data-own-mark
				class:chosen={chosen === face.id}
				use:mark={face.id}
				onclick={() => openPerson(face)}
				onmouseenter={() => (lively = face.id)}
				onmouseleave={() => (lively = lively === face.id ? null : lively)}
				onfocus={() => (lively = face.id)}
				onblur={() => (lively = lively === face.id ? null : lively)}
			>
				<!-- The still, always. A wall of them is a wall of crops that were
				     cut once and cost nothing to draw.

				     The face carried through the years is not a picture that is
				     kept but one that is MADE: eighteen seconds of warping per
				     person, the first time anybody asks. A grid that asks for a
				     hundred and twenty-three of them at once is not slow because
				     of what it downloads — it is a hundred and twenty-three
				     builds queued behind one another, which is what "no faster"
				     was. So only the one being looked at asks. -->
				<Portrait
					rung="face"
					src={face.cover ? cropOf(face.cover) : undefined}
					name={face.name}
				/>
				{#if lively === face.id}
					<!-- over the still rather than instead of it: it takes as long
					     as it takes to make, and until it is there the face that
					     was already drawn stays drawn -->
					<img class="alive" src={morphOf(face.id, TILE_FACE)} alt="" />
				{/if}
				<span class="who">{face.name}</span>
				{#if face.faces}<span class="many">{formatNumber(face.faces)}</span>{/if}
			</button>
		{/each}
		{/snippet}
	</Wall>
{:else if way === 'places' && !here && surface.isTv}
	{#snippet side(where: photos.Where | undefined, title: string, facts: string)}
		{#if where?.cover}
			<img class="picture" src={previewOf(where.cover, where.cover_turn ?? 0)} alt="" />
		{/if}
		<h3>{title}</h3>
		<p class="facts">{facts}</p>
	{/snippet}
	{#if inCountry}
		<Ledger items={inCountry.places} key={(w) => w.place} bind:at={atPlace} onpick={(w) => open(w.place)}>
			{#snippet line(w)}
				<span class="main">{w.place}</span>
				<span class="side">{formatNumber(w.photographs)}</span>
			{/snippet}
			{#snippet aside(w)}
				{@render side(w, w.place, [count(w.photographs, 'photos').text, span(w.first, w.last)].filter(Boolean).join(' · '))}
			{/snippet}
		</Ledger>
	{:else}
		<Ledger items={countries} key={(c) => c.code} bind:at={atCountry} onpick={(c) => enter(c.code)}>
			{#snippet line(c)}
				<span class="main">{c.name}</span>
				<span class="side">{formatNumber(c.photographs)}</span>
			{/snippet}
			{#snippet aside(c)}
				{@render side(
					c.cover,
					c.name,
					[count(c.places.length, 'places').text, count(c.photographs, 'photos').text, span(c.first, c.last)]
						.filter(Boolean)
						.join(' · ')
				)}
			{/snippet}
		</Ledger>
	{/if}
{:else if way === 'places' && !here}
	<!-- the map first: where the house has been is a shape before it is a list,
	     and the arrows step between the pins rather than dragging the map -->
	<PlaceMap places={wheres} onopen={open} />

	<ul class="wheres" class:tv={surface.isTv}>
		{#each wheres as where (where.place)}
			<li>
				<button onclick={() => open(where.place)}>
					<span class="name">{where.place}</span>
					<span class="many">{formatNumber(where.photographs)}</span>
				</button>
			</li>
		{/each}
	</ul>
{:else}
	{#if surface.isTv && opened}
		<!-- which place this is, and where on the earth it lies: a map for the
		     eye only, since the photographs under it are what the remote is for -->
		<div class="placed">
			<div class="glance"><PlaceMap places={[opened]} glance /></div>
			<div>
				<h2>{opened.place}</h2>
				<p class="facts">
					{[inCountry?.name, count(opened.photographs, 'photos').text, span(opened.first, opened.last)]
						.filter(Boolean)
						.join(' · ')}
				</p>
			</div>
		</div>
	{/if}
	{#if searched}
		<PhotoQuery search={searched} />
	{/if}
	{#key `${who?.id ?? ''}/${here ?? ''}/${searched}`}
		<!-- Read across a room rather than leaned into: a photograph wants to be
		     smaller here, not larger, because what a television is for is seeing
		     many of them at once. Three of a shelf of forty thousand is a shelf
		     you scroll rather than look at — and at 186px each was an UPSCALE of
		     the 350px file behind it, so it was blurry as well as sparse. -->
		<PhotoTimeline person={who?.id} place={here ?? undefined} search={searched || undefined} tile={surface.isTv ? 100 : 156} rail={surface.isTv ? 'start' : 'end'} plays={recordingOf} actions={surface.isTv ? undefined : toTv} bind:open={viewing} />
	{/key}
{/if}

{#snippet toTv(photo: Photo)}<PhotoToTv {photo} />{/snippet}
</div>
</div>


<style>
	.named {
		--head-title: var(--tenfoot-name);
	}
	.placed {
		display: flex;
		align-items: center;
		gap: 1.2rem;
		margin: 0 0 1rem;
	}
	.placed .glance {
		flex: none;
		width: 14rem;
		height: 7.5rem;
	}
	.placed h2 {
		margin: 0;
		font-size: var(--fs-2xl);
	}
	.placed .facts {
		margin: 0.2rem 0 0;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.give {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin: 0 0 1rem;
	}

	.told {
		color: var(--muted);
		font-size: var(--fs-m);
	}

	.trouble {
		color: var(--warn);
		font-size: var(--fs-m);
	}

	.face {
		border: 0;
		background: none;
		padding: 0;
		cursor: pointer;
		color: var(--text);
		display: grid;
		gap: 0.35rem;
		justify-items: center;
		position: relative;
	}

	/* exactly over the still, in the same circle: the two are the same face and
	   swapping between them should not move anything */
	.alive {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		aspect-ratio: 1;
		object-fit: cover;
		border-radius: 50%;
		pointer-events: none;
	}
	.who {
		font-size: var(--fs-m);
		text-align: center;
	}
	.many {
		font-size: var(--fs-s);
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.wheres {
		list-style: none;
		margin: 1rem 0 0;
		padding: 0;
		display: grid;
		/* NAME in cells.ts — 15rem picked against real Croatian place names */
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 0.35rem;
	}
	.wheres button {
		display: flex;
		width: 100%;
		align-items: baseline;
		gap: 0.6rem;
		padding: 0.6rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: none;
		color: var(--text);
		font: inherit;
		cursor: pointer;
		text-align: left;
	}
	.wheres button:hover,
	.wheres button:focus-visible {
		background: var(--surface);
	}
	.wheres .name {
		font-weight: 600;
	}
	.wheres .many {
		margin-left: auto;
	}
</style>
