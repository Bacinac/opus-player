<script lang="ts">
	// What one thing is, before deciding to watch it. The same panel wherever a
	// card is tapped, so a film does not open differently depending on which
	// screen found it.

	import { art, ground } from '$lib/ask/art';
	import Fanart from '$lib/tv/Fanart.svelte';
	import { formatNumber, formatTime, t } from '$lib/i18n';
	import { request, withLang } from '$lib/kit';
	import { MediaHead } from '$lib/opus';
	import { episodeLabel } from '$lib/say/episode';
	import { seasonViews } from '$lib/say/says';
	import { aboutArtist, aboutWork, streamingOn } from '$lib/say/facts';
	import { watched } from '$lib/keep/watched.svelte';
	import Cast from '$lib/parts/Cast.svelte';
	import Made from '$lib/parts/Made.svelte';
	import Copy from '$lib/parts/Copy.svelte';
	import Record from '$lib/parts/Record.svelte';
	import Discography from '$lib/parts/Discography.svelte';
	import MixInside from '$lib/parts/MixInside.svelte';
	import SeriesSeasons from '$lib/parts/SeriesSeasons.svelte';
	import { chipsOf } from '$lib/say/copy';
	import { count } from '$lib/say/count';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { hasEngine, queue } from '$lib/keep/queue.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { sleeve } from '$lib/keep/sleeve.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { focusWaiting } from '$lib/tv/spatial.svelte';
	import { nav } from '$lib/tvui/nav.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import Shelf from '$lib/tvui/Shelf.svelte';
	import Info from '$lib/tv/Info.svelte';
	import InfoPress from '$lib/tv/InfoPress.svelte';
	import { artist as putOnArtist } from '$lib/ask/puton';
	import type {
		About,
		ArtistShelf,
		Card,
		EpisodeEntry,
		ReleaseQueue,
		SeasonOffer,
		SeasonView,
		SeriesTree
	} from '$lib/keep/types';

	let {
		card,
		onclose,
		onplay,
		onwant,
		onopen
	}: {
		card: Card | null;
		onclose: () => void;
		/** stand this sheet on somebody else — the band they were in, the trio
		 *  they went on to. A related artist is somewhere to go, not a word. */
		onopen?: (c: Card) => void;
		onplay?: (c: Card) => void;
		onwant?: (c: Card, seasons: number[], only: boolean) => void;
	} = $props();

	// A series is the same panel held or not: the seasons it has, as many of them
	// open at once as you like, and the episodes under each. Held, the tree comes
	// from the library and an episode with a file can be played; unheld, TMDB
	// says what the seasons are and the episodes arrive a season at a time, as
	// they are opened. Nothing is added to the catalogue to show any of it.
	let tree = $state<SeriesTree | null>(null);
	let offer = $state<SeasonOffer | null>(null);
	let chosen = $state<string[]>([]);
	let fetched = $state<{ [season: string]: EpisodeEntry[] }>({});
	let loading = $state(false);

	let owned = $derived(tree !== null);

	$effect(() => {
		const series = card?.kind === 'series' ? card : null;
		tree = null;
		offer = null;
		chosen = [];
		fetched = {};
		asked.clear();
		if (!series) return;
		loading = true;
		const stop = new AbortController();
		void (async () => {
			if (series.owned === false) {
				const what = await request<SeasonOffer>(
					`/api/explore/series/${series.tmdb_id}/seasons`,
					{ signal: stop.signal }
				);
				// a series reached through Explore that the library already holds
				// is not a catalogue entry to be offered: what is on disk is the
				// only honest thing to show, and it is one ask away
				if (what?.in_library && what.library_id !== null) {
					tree = await request<SeriesTree>(withLang(`/api/library/series/${what.library_id}`), {
						signal: stop.signal
					});
				} else offer = what;
			} else {
				tree = await request<SeriesTree>(withLang(`/api/library/series/${series.id}`), {
					signal: stop.signal
				});
			}
			// open on the first season that has something to play, or simply the
			// first: a panel that opens with every season unfolded is a wall
			const first =
				(tree?.seasons.find((s) => s.episodes.some((e) => e.playable)) ??
					tree?.seasons[0] ??
					offer?.seasons[0])?.number;
			chosen = first === undefined ? [] : [String(first)];
			loading = false;
		})();
		return () => stop.abort();
	});

	// which seasons have been sent for, kept out of the reactive graph so asking
	// for one does not count as a reason to ask again
	const asked = new Set<string>();

	$effect(() => {
		const id = card?.kind === 'series' && card.owned === false && !tree ? card.tmdb_id : null;
		if (!id) return;
		for (const key of chosen) {
			if (asked.has(key)) continue;
			asked.add(key);
			void request<EpisodeEntry[]>(`/api/explore/series/${id}/season/${key}`).then((episodes) => {
				// a season that arrives after its series was put away is nobody's
				if (card?.tmdb_id !== id) return;
				if (episodes) fetched = { ...fetched, [key]: episodes };
				else asked.delete(key);
			});
		}
	});

	let seasons = $derived<SeasonView[]>(
		tree
			? seasonViews(tree)
			: (offer?.seasons ?? []).map((s) => ({
					number: s.number,
					episodes: fetched[String(s.number)] ?? [],
					total: s.episodes,
					have: 0
				}))
	);
	let open = $derived(seasons.filter((s) => chosen.includes(String(s.number))));

	let wanted = $derived(open.reduce((n, s) => n + (s.total - s.have), 0));
	// Either we hold it or we do not, and the two are never offered at once. A
	// film with a file on disk plays — including one still waiting for its
	// subtitle, which is a film we have. One with no file is asked for, whether
	// it is on a shelf as something wanted or on Explore as something found.
	const held = $derived(card?.state === 'complete' || card?.state === 'waiting_subtitles');
	let missing = $derived(seasons.reduce((n, s) => n + (s.total - s.have), 0));
	// A person is never asked for — not an actor, not a director, not a
	// recording artist. A career is terabytes; what somebody means when they
	// point at somebody is one of their works, and every work has its own.
	let askable = $derived(
		!!onwant && !card?.person && (card?.kind === 'series' ? missing > 0 : !held)
	);
	// A person is neither played nor asked for, so there is no row of things to
	// do over their portrait — and an empty one is a band of shadow lying across
	// a picture for no reason at all.
	// A film watched somewhere else, or one the credits were talked over: seen is
	// a thing a person says as well as a thing a player notices.
	const sayable = $derived(
		card && ['movie', 'episode'].includes(card.kind) ? card : null
	);
	const seen = $derived(Boolean(sayable && watched.has(sayable.kind, sayable.id)));

	$effect(() => {
		if (sayable) watched.ask(sayable.kind, [sayable.id]);
	});

	let doable = $derived(
		(!!onplay && held && ['movie', 'episode'].includes(card?.kind ?? '')) || askable
	);

	/** A screen that opens takes the remote with it. The card it was pressed on
	 *  leaves the page with the shelf, so without this the remote is left on
	 *  nothing and no arrow moves: an artist's records were on the screen and
	 *  unreachable — which they were again, because the one ask happened before
	 *  the library had answered with them. */
	$effect(() => {
		if (!card || !surface.isTv) return;
		const stop = focusWaiting('.panel .go, .panel button.record, .panel .episode, .panel button');
		const at = setTimeout(
			() => document.querySelector<HTMLElement>('.sheet .actions')?.scrollIntoView({ block: 'nearest' }),
			120
		);
		return () => {
			stop();
			clearTimeout(at);
		};
	});

	let shelf = $state<ArtistShelf | null>(null);
	let album = $state<ReleaseQueue | null>(null);

	/** An artist on a television is one shelf: the records the house holds, as
	 *  sleeves, newest first. A sleeve is how anybody finds the record they
	 *  meant — a column of names in a row of equal buttons is a form, and ten
	 *  feet away it is unreadable.
	 *
	 *  What they made and we do not hold is behind INFO with the rest of what
	 *  this page does not say. It was a second shelf under this one, and a
	 *  second row is a second place the arrows have to get out of for something
	 *  nobody came here to look at. */
	const onShelf = $derived(
		(shelf?.releases ?? []).map((r) => ({
			id: r.id,
			title: r.title,
			cover: r.cover,
			quiet: [r.year, r.tracks ? count(r.tracks, 'songs').text : ''].filter(Boolean).join(' · ')
		}))
	);

	// the whole of what a thing is, asked for when this panel opens rather than
	// carried by every card on the shelf behind it — and for a series, said by
	// the same answer that brought its seasons
	let told = $state<About | null>(null);
	const about = $derived(card?.kind === 'series' ? (tree?.about ?? null) : told);

	$effect(() => {
		// an Explore card is not ours, and a series says it with its seasons
		const what =
			card && ['movie', 'episode'].includes(card.kind) && card.owned !== false ? card : null;
		told = null;
		if (!what) return;
		const stop = new AbortController();
		void request<About>(withLang(`/api/library/about/${what.kind}/${what.id}`), {
			signal: stop.signal
		}).then((found) => (told = found));
		return () => stop.abort();
	});

	// where it was left, so the time it would end is read from there
	let resumeAt = $state(0);
	$effect(() => {
		const what =
			card && ['movie', 'episode'].includes(card.kind) && card.owned !== false ? card : null;
		resumeAt = 0;
		if (!what) return;
		const stop = new AbortController();
		void request<{ position_s: number; watched: boolean }>(`/api/progress/${what.kind}/${what.id}`, {
			signal: stop.signal
		}).then((mark) => {
			if (mark && !mark.watched && mark.position_s > 10) resumeAt = mark.position_s;
		});
		return () => stop.abort();
	});
	let now = $state(Date.now());
	$effect(() => {
		const beat = setInterval(() => (now = Date.now()), 15000);
		return () => clearInterval(beat);
	});
	const ends = $derived(
		about?.file?.duration_s
			? formatTime(new Date(now + (about.file.duration_s - resumeAt) * 1000))
			: ''
	);

	// what a film IS, and then what this copy of it is — the second question a
	// person asks about something they are deciding to watch tonight
	// a person is not measured in minutes and genres
	// An artist's line is read off the shelf once it has answered: it is fresher
	// than the card, and a card the page built for itself — a band opened from
	// the name of the one before it — carries none of this at all. The biography
	// goes the same way and for a harder reason: what a listing carries is a
	// `blurb`, three hundred characters ending in an ellipsis, and preferring it
	// left the page showing a sentence that stops mid-word with nothing behind
	// it. The shelf carries the whole thing.
	const facts = $derived(
		card?.kind !== 'artist'
			? [aboutWork(about), streamingOn(card)].filter(Boolean).join(' · ')
			: aboutArtist(
					shelf
						? {
								...card,
								year: shelf.begin_year ?? card.year,
								end_year: shelf.end_year ?? card.end_year,
								country: shelf.country ?? card.country,
								country_hr: shelf.country_hr ?? card.country_hr,
								releases: shelf.releases_total
							}
						: card
				)
	);

	const copy = $derived(chipsOf(about, page.url.pathname));
	const overview = $derived(
		card?.kind === 'artist' ? shelf?.bio || card.overview || '' : about?.overview || card?.overview || ''
	);
	// ten feet away the page says a name, a line and what to do; the rest waits
	// behind INFO
	let info = $state(false);
	$effect(() => {
		void card;
		info = false;
	});
	const amount = $derived(
		!surface.isTv
			? ''
			: card?.kind === 'artist' && shelf
				? formatNumber(shelf.releases.length)
				: card?.kind === 'series' && seasons.length
					? formatNumber(seasons.length)
					: ''
	);
	// the same decision the frame makes about what lies behind a page: its wide
	// picture where there is one, and its poster thrown out of focus where there
	// is not
	const behind = $derived(card ? ground(card) : null);

	// an artist card is a face; what plays is a record, so opening one fetches
	// the shelf and opening a record fetches the songs on it
	$effect(() => {
		const id = card?.kind === 'artist' ? card.id : null;
		shelf = null;
		album = null;
		if (id === null) return;
		loading = true;
		const stop = new AbortController();
		void request<ArtistShelf>(withLang(`/api/library/artist/${id}`), { signal: stop.signal }).then(
			(found) => {
				shelf = found;
				loading = false;
				// arrived from a record in a row: the page opens at that record
				if (found && card?.release_id) void openAlbum(card.release_id);
			}
		);
		return () => stop.abort();
	});

	// Back takes away one thing at a time: the record first, then the artist it
	// was on, then the shelf. It was two presses for one, because this screen
	// answered Escape itself as well as through the ladder — the second one fell
	// through to "nothing is standing over anything" and left for the home
	// screen from an artist nobody had finished with.
	// while it is up it IS the screen, so the menu is not drawn beside it and the
	// column it keeps is not reserved
	$effect(() => (card ? nav.takes() : undefined));

	$effect(() =>
		onBack(
			() => {
				if (!album) return false;
				album = null;
				return true;
			},
			() => !!album
		)
	);

	// while a record is on this screen, putting it on does not open a second copy
	$effect(() => {
		sleeve.onScreen = album?.id ?? null;
		return () => (sleeve.onScreen = null);
	});

	async function openAlbum(releaseId: number) {
		// ask for the edition this screen can actually play
		const prefer = hasEngine() ? 'surround' : 'stereo';
		const found = await request<ReleaseQueue>(`/api/library/release/${releaseId}?prefer=${prefer}`);
		if (found) album = found;
	}

	function playEpisode(season: SeasonView, episode: EpisodeEntry) {
		if (!onplay || !tree) return;
		onplay({
			kind: 'episode',
			id: episode.id,
			series_id: tree.id,
			title: tree.title,
			subtitle: episodeLabel(season.number, episode),
			image: tree.image,
			backdrop: tree.backdrop,
			state: episode.state,
			overview: ''
		});
	}

</script>

{#if card}
	<div
		class="sheet"
		class:tv={surface.isTv}
		data-holds-remote
		role="presentation"
		onclick={onclose}
	>
		{#if surface.isTv && behind}
			<!-- The screen about one thing stands on that thing's own picture, whole,
			     the way the shelf stands on the section's. It was a dark crop inside
			     the panel instead, which is what made the panel read as a card lying
			     on an empty screen — and the ten-foot layouts this is measured off
			     have no cards at all: the words lie on the picture. -->
			<div class="stage" aria-hidden="true">
				<Fanart art={behind} wash={!card.backdrop} />
			</div>
		{/if}
		<div class="panel" role="presentation" onclick={(e) => e.stopPropagation()}>
			{#snippet madeBy()}
				<Made people={about?.directors ?? []} />
			{/snippet}

			{#snippet whatToDo()}
				{#if surface.isTv && card.kind === 'artist'}
					<Press tone="go" onclick={() => putOnArtist(card.id)}>{t('card.play')}</Press>
					<Press onclick={() => putOnArtist(card.id, true)}>{t('music.shuffle')}</Press>
				{/if}
				{#if onplay && held && (card.kind === 'movie' || card.kind === 'episode')}
					<Press tone="go" onclick={() => onplay(card)}>{t('card.play')}</Press>
					{#if ends}<span class="ends">{t('play.ends', { time: ends })}</span>{/if}
				{/if}
				{#if sayable}
					<Press
						onclick={() => watched.say(sayable.kind, [sayable.id], !seen, sayable.series_id)}
					>
						{seen ? t('series.unmark') : t('series.mark')}
					</Press>
				{/if}
				{#if askable && onwant}
					{#if card.kind === 'series'}
						<Press
							tone="go"
							disabled={wanted === 0}
							onclick={() => onwant(card, chosen.map(Number), !owned)}
						>
							{t('explore.want')}
						</Press>
						<Press tone="go" onclick={() => onwant(card, [], false)}>
							{t('explore.wantAll')}
						</Press>
					{:else}
						<Press tone="go" onclick={() => onwant(card, [], false)}>
							{t('explore.want')}
						</Press>
					{/if}
				{/if}
				{#if surface.isTv}<InfoPress onclick={() => (info = true)} />{/if}
			{/snippet}

			<!-- The same head every page about one thing opens with, the series' own
			     page included: its picture behind it, its poster beside it, and what
			     may be done about it under the words. -->
			{#if album}
				<!-- a record, drawn the one way a record is drawn on this player -->
				<Record
					tracks={album.tracks}
					cover={album.cover_url}
					album={album.title}
					artist={album.artist}
					releaseId={album.id}
					year={album.release_date?.slice(0, 4) ?? ''}
					playing={queue.current?.release_id === album.id ? queue.index : -1}
					going={queue.playing}
					onplay={(i, at) => queue.play(album!.tracks, i, at)}
				/>
			{:else}
			<div class="named">
			<MediaHead
				title={card.title}
				subtitle={facts}
				{amount}
				overview={surface.isTv && card.kind === 'artist' ? '' : overview}
				poster={surface.isTv ? null : art(card.image ?? shelf?.image ?? null, 400)}
				backdrop={art(card.backdrop, 780)}
				round={Boolean(card.round)}
				under={!surface.isTv && about?.directors?.length ? madeBy : undefined}
				actions={doable || surface.isTv ? whatToDo : undefined}
			/>
			</div>
			{/if}
			{#if surface.isTv}
				<Info bind:open={info} title={card.title} {overview}>
					{#if about?.directors?.length}{@render madeBy()}{/if}
					<Copy chips={copy} />
					{#if card.kind === 'artist' && shelf}
						<Discography {shelf} part="aside" album={false} onalbum={openAlbum} {onopen} onshelf={(found) => (shelf = found)} />
					{/if}
				</Info>
			{/if}

			<div class="open" class:under={album !== null}>
				<MixInside {card} {onwant} />

				<!-- What this copy of it is comes before who is in it: a person
				     deciding what to watch tonight asks whether this is the good
				     copy, and the billing is what they read after that. -->
				{#if !surface.isTv}<div class="across"><Copy chips={copy} /></div>{/if}

				<div class="across"><Cast people={about?.cast ?? []} /></div>


				{#if card.kind === 'series' || card.kind === 'artist'}
					<div class="more">
					{#if card.kind === 'series'}
						{#if loading}
							<p class="muted">{t('common.loading')}</p>
						{:else if seasons.length}
							<SeriesSeasons
								{seasons}
								bind:chosen
								{owned}
								{wanted}
								onget={onwant && ((season) => onwant(card, [season], false))}
								onplay={playEpisode}
							/>
						{:else}
							<p class="muted">{t('sheet.noEpisodes')}</p>
						{/if}
					{/if}

				{#if card.kind === 'artist'}
					{#if loading}
						<p class="muted">{t('common.loading')}</p>
					<!-- an artist with nothing on the shelf still has a page: what they
					     made and we do not hold is the whole point of the second row,
					     and hanging the block on held records hid it exactly there -->
					{:else if surface.isTv && shelf}
						<!-- The records, and nothing above them. The band a singer plays
						     in is behind INFO with the records nobody here holds: the
						     first press on this page is meant for an album, and a line
						     standing over the shelf is a press spent on the way. -->
						{#if onShelf.length}
							<Shelf
								label={t('music.albums')}
								note={count(onShelf.length, 'releases').text}
								sleeves={onShelf}
								onpick={(sleeve) => openAlbum(sleeve.id)}
							/>
						{:else}
							<p class="muted">{t('sheet.noneHeld')}</p>
						{/if}
					{:else if shelf && (shelf.releases.length || shelf.missing.length)}
						<Discography
							{shelf}
							album={album !== null}
							onalbum={openAlbum}
							{onopen}
							onshelf={(found) => (shelf = found)}
						/>
					{:else}
						<p class="muted">{t('sheet.noAlbums')}</p>
					{/if}
				{/if}
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	/* ten feet away a name is what the page is, and nothing else is competing
	   with it for the top of the screen */
	.tv .named {
		--head-title: var(--tenfoot-name);
	}
	.ends {
		align-self: center;
		font-variant-numeric: tabular-nums;
		color: var(--muted);
		white-space: nowrap;
	}
	/* not an overlay: a part of the page, standing where the shelf stood, under
	   the panel that already introduced what it is about */
	.sheet {
		display: block;
	}
	/* On a television this is the second level, and a second level takes the
	   screen: fixed at inset 0 rather than laid inside the frame's padded box,
	   which is what made it 665px of a 960px screen. The menu keeps its column
	   UNDERNEATH — covered, not removed — so the six things that reserve room
	   for that column go on reserving it and none of them has to be taught that
	   it is sometimes not there. A commit once removed it on four screens out of
	   five and left all six reserving anyway; this cannot repeat that. */
	/* What the screen is about stays put and only the list under it moves. The
	   stage scrolled whole, so a band with thirty records or a series with twelve
	   seasons carried its own poster, name and description off the top of the
	   screen the moment anybody looked past the first row — and what a person is
	   reading while they walk a list is exactly that description. */
	.sheet.tv {
		position: fixed;
		inset: 0;
		z-index: var(--z-stage, 30);
		overflow: hidden;
		background: var(--bg);
		/* --tenfoot-top is the menu screen's distance to its first poster row, and
		   the rail is its only other reader. A stage that covers the rail was
		   reserving 108px for a band it draws over. */
		padding: var(--tenfoot-pad, 3rem) var(--tenfoot-pad, 3rem)
			calc(var(--tv-bar-h, 0px) + var(--tenfoot-safe-y, 1.7rem));
	}
	/* Three columns that fill the screen and do not scroll: the poster, what it
	   is and what you can do with it, and who is in it down the side. */
	/* Stacked, not columned. What it is comes first beside its poster, then who
	   is in it, and what this copy of it is along the bottom — read down the
	   page rather than across three of them.

	   Rows are not named: a named row keeps its gap whether or not this kind of
	   thing has anything to put in it, and an artist — who has no cast and no
	   file — was left with four empty rows' worth of air above their records
	   while a film's cast began directly under the poster. */
	.open {
		display: grid;
		grid-template-columns: minmax(0, 12rem) minmax(0, 1fr);
		gap: 1.4rem 1.6rem;
		align-items: start;
	}
	/* Ten feet away this is a card and a card has to fit the screen it is drawn
	   on: what a film is, what this copy of it is and who is in it, with nothing
	   under the bottom edge. The air between them is the first thing to give. */
	.tv .open {
		gap: 0.8rem 1.6rem;
	}
	/* what this kind of thing has that the others do not: a series' seasons, an
	   artist's records. In the grid rather than under it, so every kind of
	   screen keeps one rhythm down the page */
	.more {
		grid-column: 1 / -1;
		min-width: 0;
	}
	/* A row of faces is the cast and a row of chips is the file; saying so cost
	   a line of the screen each, and the screen is what a person is reading. The
	   one block that is not obvious from looking at it keeps its name. */
	.across {
		grid-column: 1 / -1;
	}
	/* a row with nothing in it renders nothing, and an empty grid row still
	   keeps the gap above it */
	.across:empty {
		display: none;
	}
	.panel {
		width: 100%;
	}
	.tv .panel {
		font-size: var(--fs-l);
		/* over the picture the stage lies on, rather than under it */
		position: relative;
		z-index: 1;
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}
	/* the one thing on this screen that scrolls */
	.tv .open {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		overflow-x: hidden;
		/* room for the ring, which is drawn outside the key it is around */
		padding: 0.4rem 0.5rem;
		margin: 0 -0.5rem;
	}
	/* under an open record the songs are what is walked, and they take the room */
	.tv .open.under {
		display: none;
	}
	/* fixed, not absolute: the stage scrolls, and a picture that scrolls with a
	   page is a picture that leaves it */
	.stage {
		position: fixed;
		inset: 0;
		z-index: 0;
		pointer-events: none;
	}
	/* A shelf writes down one side of its picture; a screen about one thing
	   writes across two thirds of it — a title, five lines of description and a
	   row of buttons. So the same veil is drawn once more over the half being
	   written on, and the picture is left alone where it is worth seeing. */
	.stage::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(
			to right,
			color-mix(in srgb, var(--bg) 62%, transparent) 0%,
			color-mix(in srgb, var(--bg) 46%, transparent) 55%,
			transparent 92%
		);
	}
</style>
