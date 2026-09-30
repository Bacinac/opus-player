<script lang="ts">
	// A series the house holds: what it is, its seasons, the episodes of one of
	// them, and what pressing any of that does.
	//
	// One screen, both surfaces. It was a page of drawers here and a walk
	// through levels on the television, each with its own idea of what a line
	// said — so the same ignored season read two different ways. Both surfaces
	// now draw the same seasons and lines from the one set of words below; a
	// sofa only gets them in a row it can walk with a remote.

	import { art } from '$lib/ask/art';
	import { goto } from '$app/navigation';
	import { onBack } from '$lib/keep/back.svelte';
	import {
		Button,
		Icon,
		request,
		Tag,
		withLang
	} from '$lib/kit';
	import {
		EpisodeRow,
		MediaHead,
		type PageSeason,
		SeriesPage,
		StateMark,
		Tally
	} from '$lib/opus';
	import Press from '$lib/tvui/Press.svelte';
	import Split from '$lib/tvui/Split.svelte';
	import Play from '$lib/screens/Play.svelte';
	import { askEpisode, want } from '$lib/ask/want';
	import Cast from '$lib/parts/Cast.svelte';
	import Copy from '$lib/parts/Copy.svelte';
	import Made from '$lib/parts/Made.svelte';
	import { chipsOf } from '$lib/say/copy';
	import { aboutWork } from '$lib/say/facts';
	import { watched } from '$lib/keep/watched.svelte';
	import { page } from '$app/state';
	import { aired, episodeLabel } from '$lib/say/episode';
	import {
		episodeName,
		episodeTags,
		haveOf,
		seasonCounts,
		seasonMark,
		seasonName,
		seasonViews
	} from '$lib/say/says';
	import { formatDate, formatNumber, t } from '$lib/i18n';
	import { surface } from '$lib/keep/surface.svelte';
	import { hero } from '$lib/keep/hero.svelte';
	import Info from '$lib/tv/Info.svelte';
	import InfoPress from '$lib/tv/InfoPress.svelte';
	import type { Card, EpisodeEntry, SeasonView, SeriesTree } from '$lib/keep/types';

	let { id }: { id: number } = $props();

	let tree = $state<SeriesTree | null>(null);
	// what a film's screen says about itself, which a series is owed too: when it
	// is from and what kind of thing it is, who made it, who is in it
	const about = $derived(tree?.about ?? null);
	let loaded = $state(false);
	let problem = $state('');
	let playing = $state<Card | null>(null);
	/** which season is showing */
	let shown = $state<string | number | null>(null);

	async function load() {
		const asked = id;
		let why = '';
		const found = await request<SeriesTree>(withLang(`/api/library/series/${asked}`), {}, {
			on: { 404: () => {} },
			failed: (detail) => (why = detail)
		});
		// a series opened after this one was asked for is the one on the screen
		if (asked !== id) return;
		tree = found;
		problem = why;
		// who has seen what is the player's own, and asked for the whole tree at
		// once rather than a question per line
		if (tree) await watched.ask('episode', tree.seasons.flatMap((s) => s.episodes.map((e) => e.id)));
		if (asked !== id) return;
		if (tree && !tree.seasons.some((s) => s.number === shown)) shown = nextSeason(tree);
		loaded = true;
	}

	$effect(() => {
		id;
		load();
	});

	// The way out is the frame's one Back. The page has no levels on either
	// surface: a television hands Back to the shelf behind it, a desk goes to
	// the list of series.
	$effect(() =>
		onBack(
			() => {
				if (surface.isTv) return false;
				goto('/series');
				return true;
			},
			() => !surface.isTv
		)
	);

	/** Where this profile is in a series: the episode it is part way through,
	 *  else the first one here after the last it finished, else the first one
	 *  here it has not seen. A stray old episode of a season it never watched
	 *  is not where it is. */
	function resumeAt(of: SeriesTree | null): { season: number; episode: EpisodeEntry } | null {
		const lines = (of?.seasons ?? []).flatMap((s) => s.episodes.map((episode) => ({ season: s.number, episode })));
		const open = (e: EpisodeEntry) => e.playable && !watched.has('episode', e.id);
		const started = lines.find(({ episode }) => open(episode) && watched.part('episode', episode.id) > 0);
		if (started) return started;
		const last = lines.findLastIndex(({ episode }) => watched.has('episode', episode.id));
		return lines.slice(last + 1).find(({ episode }) => open(episode)) ?? lines.find(({ episode }) => open(episode)) ?? null;
	}

	function nextSeason(of: SeriesTree): number | null {
		return resumeAt(of)?.season ?? of.seasons[0]?.number ?? null;
	}

	const card = $derived<Card>({
		kind: 'series',
		id: tree?.id ?? 0,
		title: tree?.title ?? '',
		image: tree?.image ?? null,
		backdrop: tree?.backdrop ?? null,
		state: null,
		overview: tree?.overview ?? ''
	});

	// What lies behind a page is what the page is about. Arriving off a poster
	// the frame already has it; opened cold at its own address it had nothing,
	// and fell back to the first card of the SHELF — another series' picture
	// behind this one's name. Hushed, because being put here is not the remote
	// asking to be told about it.
	$effect(() => {
		if (!tree || !surface.isTv) return;
		hero.hush();
		hero.show(card);
	});

	const seasons = $derived<SeasonView[]>(seasonViews(tree));

	/** The same seasons in the shape the shared page takes. Every word in here
	 *  comes from `says`; nothing is decided a second time. */
	const pages = $derived<PageSeason[]>(
		seasons.map((one) => ({
			key: one.number,
			title: seasonName(one.number),
			counts: seasonCounts(one),
			episodes: one.episodes.map((e) => ({
				key: e.number,
				number: e.number,
				title: episodeName(one.number, e),
				description: e.overview ?? '',
				image: e.still ? art(e.still, 320) : null,
				runtime: e.runtime_min ?? null,
				seen: watched.has('episode', e.id) ? t('series.seen') : '',
				part: watched.part('episode', e.id),
				dim: !e.playable,
				// Pressing a line does the one thing that line allows: watch it if
				// it is here, go and look for it if it is not, and say when it is
				// due if it has not been broadcast yet.
				onpick: e.playable
					? () => play(one.number, e)
					: async () => {
							if (await askEpisode(e, one.number)) await load();
						},
				note: e.air_date && !aired(e) ? formatDate(e.air_date) : '',
				tags: episodeTags(one, e)
			}))
		}))
	);

	let have = $derived((tree?.seasons ?? []).flatMap((s) => s.episodes).filter((e) => e.playable).length);
	let total = $derived((tree?.seasons ?? []).reduce((n, s) => n + s.episodes.length, 0));
	// The seasons the library is still following. A season watched and then
	// deleted is not a season with something missing from it — the catalogue is
	// where that is said, and the player reads it rather than deciding again.
	let followed = $derived((tree?.seasons ?? []).filter((s) => s.followed));
	// What is missing, could be found, and is still being followed: the library
	// declines what has not been broadcast, so counting that here would offer
	// forty-two and fetch thirty-five.
	let wanted = $derived(
		followed.flatMap((s) => s.episodes).filter((e) => !e.playable && aired(e)).length
	);

	let info = $state(false);

	const current = $derived(pages.find((one) => one.key === shown) ?? pages[0] ?? null);
	const currentView = $derived(seasons.find((one) => one.number === current?.key) ?? null);
	let rowsBox = $state<HTMLElement | null>(null);
	// another season's episodes start at their first, not where the last ones were left
	$effect(() => {
		void current?.key;
		if (rowsBox) rowsBox.scrollTop = 0;
	});

	function play(seasonNumber: number, episode: EpisodeEntry) {
		if (!tree) return;
		playing = {
			kind: 'episode',
			id: episode.id,
			series_id: tree.id,
			title: tree.title,
			subtitle: episodeLabel(seasonNumber, episode),
			image: tree.image,
			backdrop: tree.backdrop,
			state: episode.state,
			overview: ''
		};
	}

	async function fetchMissing(wanted: number[]) {
		if (!tree) return;
		await want(
			{
				kind: 'series',
				id: tree.id,
				tmdb_id: tree.tmdb_id,
				title: tree.title,
				image: tree.image,
				backdrop: tree.backdrop,
				state: null,
				overview: tree.overview
			},
			wanted,
			false
		);
		await load();
	}
</script>

{#if loaded && tree}
	{#snippet madeBy()}
		<Made people={about?.directors ?? []} />
	{/snippet}

	{#snippet missing()}
		<!-- One sentence for the whole of what is not here. What is followed is
		     decided in the Library; this only fetches what following has left
		     behind. -->
		{#if surface.isTv}
			<Press onclick={() => fetchMissing(followed.map((one) => one.number))}>
				{t('series.getMissing', { n: formatNumber(wanted) })}
			</Press>
		{:else}
			<Button tone="primary" onclick={() => fetchMissing(followed.map((one) => one.number))}>
				{t('series.getMissing', { n: formatNumber(wanted) })}
			</Button>
		{/if}
	{/snippet}

	{#snippet marks(which: PageSeason)}
		{@const one = seasons.find((each) => each.number === Number(which.key))}
		{@const mark = one ? seasonMark(one) : null}
		{#if mark?.show}
			<Button
				selected={mark.clearing}
				title={mark.label}
				label={mark.label}
				onclick={() => watched.say('episode', mark.ids, !mark.clearing, tree?.id)}
			>
				<Icon name="check" size={16} />
			</Button>
		{/if}
	{/snippet}

	{#if surface.isTv}
		<!-- Ten feet away it is the desk's page, read with a remote: the series
		     above, its seasons down the left, and the episodes of the season the
		     remote stands on beside them. Landing on a season shows it — there is
		     no level to go into and come back out of, so Back is the shelf's.
		     The seasons are a column and not a row across the top: a row of a
		     long series wrapped into lines that left the screen one episode. -->
		<div class="screen">
			<div class="named">
				<MediaHead
					title={tree.title}
					amount={formatNumber(seasons.length)}
					subtitle={aboutWork(about) || String(tree.year ?? '')}
				>
					{#snippet actions()}
						{#if wanted}{@render missing()}{/if}
						<InfoPress onclick={() => (info = true)} />
					{/snippet}
				</MediaHead>
			</div>
			<Info bind:open={info} title={tree.title} overview={tree.overview}>
				{@const chips = chipsOf(about, page.url.pathname)}
				<dl class="about">
					{#if total}
						<dt>{t('sheet.episodes')}</dt>
						<dd>{formatNumber(have)} / {formatNumber(total)}</dd>
					{/if}
					{#if about?.directors?.length}
						<dt>{about.directors.length > 1 ? t('play.directors') : t('play.director')}</dt>
						<dd><Made people={about.directors} said={false} /></dd>
					{/if}
					{#if chips.length}
						<dt>{t('find.studios')}</dt>
						<dd><Copy {chips} /></dd>
					{/if}
					{#if about?.cast?.length}
						<dt>{t('find.actors')}</dt>
						<dd><Cast people={about.cast} /></dd>
					{/if}
				</dl>
			</Info>
			{#if current}
				<Split bind:rows={rowsBox}>
					{#snippet parts()}
						{#each pages as one (one.key)}
							<Press
								tone="pill"
								on={one.key === current.key}
								onfocus={() => (shown = one.key)}
								onclick={() => (shown = one.key)}
							>
								{one.title}
								{#if one.counts?.length}<span class="counts"><Tally counts={one.counts} /></span>{/if}
							</Press>
						{/each}
						{#if currentView}
							{@const mark = seasonMark(currentView)}
							{@const lacking = currentView.followed
								? currentView.episodes.filter((e) => !e.playable && aired(e)).length
								: 0}
							{#if mark.show}
								<Press onclick={() => watched.say('episode', mark.ids, !mark.clearing, tree?.id)}>
									{mark.label}
								</Press>
							{/if}
							{#if lacking}
								<Press onclick={() => fetchMissing([currentView.number])}>
									{t('sheet.getSeason', { n: formatNumber(lacking) })}
								</Press>
							{/if}
						{/if}
					{/snippet}
					{#snippet held()}
						{#each current.episodes as e (e.key)}
							<EpisodeRow
								number={e.number}
								title={e.title}
								description={e.description ?? ''}
								image={e.image ?? null}
								runtime={e.runtime ?? null}
								seen={e.seen ?? ''}
								part={e.part ?? 0}
								dim={e.dim ?? false}
								onpick={e.onpick}
							>
								{#snippet meta()}
									{#if e.note}<span class="note">{e.note}</span>{/if}
									{#each e.tags ?? [] as tag (tag.text)}
										{#if tag.icon}
											<StateMark icon={tag.icon} tone={tag.tone} text={tag.title ? `${tag.text} · ${tag.title}` : tag.text} />
										{:else}
											<Tag tone={tag.tone ?? 'fact'} title={tag.title ?? ''}>{tag.text}</Tag>
										{/if}
									{/each}
								{/snippet}
							</EpisodeRow>
						{/each}
					{/snippet}
				</Split>
			{:else}
				<p class="muted">{t('sheet.noEpisodes')}</p>
			{/if}
		</div>
	{:else}
		<!-- On a desk it is the page both other modules draw for a series, so a
		     season reads here exactly as it reads in the Library. What the lines
		     say is decided in one place and handed to whichever of the two is
		     drawing them. -->
		<SeriesPage
			title={tree.title}
			subtitle={aboutWork(about) || String(tree.year ?? '')}
			overview={tree.overview}
			poster={art(tree.image, 400)}
			backdrop={art(tree.backdrop, 780)}
			count={total ? haveOf(have, total) : ''}
			seasons={pages}
			bind:season={shown}
		>
			{#snippet under()}{@render madeBy()}{/snippet}
			{#snippet seasonActions(which)}{@render marks(which)}{/snippet}
			{#snippet before()}
				<div class="across"><Copy chips={chipsOf(about, page.url.pathname)} /></div>
				<div class="across"><Cast people={about?.cast ?? []} /></div>
			{/snippet}
			{#snippet controls()}
				{#if wanted}{@render missing()}{:else}<span></span>{/if}
			{/snippet}
		</SeriesPage>
	{/if}
{:else if loaded && problem}
	<p class="muted">{t('home.libraryDown', { detail: problem })}</p>
{:else if loaded}
	<p class="muted">{t('series.gone')}</p>
{/if}

{#if playing}
	<Play card={playing} onclose={() => (playing = null)} />
{/if}

<style>
	.named {
		--head-title: var(--tenfoot-name);
	}
	/* the ways into the series stand beside its name, not on a line of their
	   own: every row the head keeps is a season or an episode fewer */
	.named :global(.what) {
		flex: 1;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		column-gap: 2rem;
	}
	.named :global(.what > *) {
		grid-column: 1;
	}
	.named :global(.what > .actions) {
		grid-column: 2;
		grid-row: 1;
		margin: 0;
	}
	.named :global(.what > .actions) {
		justify-self: end;
	}
	.about {
		display: grid;
		grid-template-columns: 8rem minmax(0, 1fr);
		align-items: center;
		gap: 0.9rem 1.5rem;
		margin: 0.4rem 0 0;
	}
	.about dt {
		color: var(--muted);
		font-size: var(--fs-m);
	}
	.about dd {
		margin: 0;
		min-width: 0;
	}
	.about dd :global(.by) {
		margin: 0;
	}
	/* a row with nothing in it renders nothing, and the space above it should go
	   with it */
	.across:not(:empty) {
		margin-bottom: 1.2rem;
	}
	.note {
		color: var(--muted);
		font-size: var(--fs-m);
	}
</style>
