<script lang="ts">
	// The record, full screen: its sleeve, the songs on it, and the words being
	// sung. What a person chose was an album, so this is what choosing one
	// answers with — the bar along the bottom is the same record made small, for
	// when they have gone off to look at something else.
	//
	// It draws; it does not drive. The element that plays, the progress that is
	// kept and the device the sound goes to all live in the bar, which hands the
	// transport in — two players for one record is how a pause stops agreeing
	// with what is on the screen.

	import { formatNumber, t } from '$lib/i18n';
	import { art } from '$lib/ask/art';
	import { cssUrl, Icon } from '$lib/kit';
	import { cast } from '$lib/keep/cast.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { focusContent, focusFirst } from '$lib/tv/spatial.svelte';
	import { lyrics } from '$lib/keep/lyrics.svelte';
	import Record from '$lib/parts/Record.svelte';
	import Words from '$lib/parts/Words.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import Turntable from '$lib/tvui/Turntable.svelte';
	import { queue, type QueueTrack } from '$lib/keep/queue.svelte';
	import { sleeve } from '$lib/keep/sleeve.svelte';
	import { surface } from '$lib/keep/surface.svelte';

	let {
		elapsed = 0,
		total = 0,
		going = false,
		toggle,
		forward,
		back,
		seek,
		shut
	}: {
		elapsed: number;
		total: number;
		going: boolean;
		toggle: () => void;
		forward: () => void;
		back: () => void;
		seek: (to: number) => void;
		shut: () => void;
	} = $props();

	const track = $derived(queue.current);
	// a device carrying the queue is the one that knows what is on it
	const artist = $derived(cast.casting && cast.artist ? cast.artist : (track?.artist ?? ''));
	const album = $derived(cast.casting && cast.album ? cast.album : (track?.album ?? ''));

	/** A record goes on, and the record is what fills the screen.
	 *
	 *  Every way of starting one hands the queue a NEW list, so a new list is
	 *  the event — pressing the fourth song of the album already on does not
	 *  reopen this over the page somebody went to. The exception is the queue
	 *  the streamer was already playing when this page loaded, which nobody
	 *  here pressed anything to start; it has no catalogue ids, and arriving to
	 *  a full screen you did not ask for is not what opening an app means. */
	/** A station is not a record and must not be dressed as one: it has no
	 *  second song, no words, no sleeve notes and no end to scrub towards. What
	 *  it has is a name, whatever is on it at this moment, and a way to stop. */
	const station = $derived(track && (track.url || track.live) ? track : null);
	const dial = $derived(station ? station.album || station.title : '');
	const onAir = $derived(
		cast.casting
			? [cast.title, cast.artist].filter(Boolean).join(' · ')
			: station && station.title !== dial
				? station.title
				: ''
	);

	/** Made small rather than closed: the record plays on and the bar along the
	 *  bottom is what is left of it, so that is where the remote goes. Left to
	 *  the browser it goes nowhere — the button it was on has just been removed
	 *  from the screen — and the next press lands wherever a corner of nothing
	 *  happens to point. */
	function shrink() {
		sleeve.hide();
		if (surface.isTv) queueMicrotask(() => focusFirst('[data-control="toggle"]'));
	}

	let known: QueueTrack[] | null = null;
	$effect(() => {
		const tracks = queue.tracks;
		if (tracks === known) return;
		known = tracks;
		// The record played through and the queue let it go. This screen is about
		// a record, so it goes with it — and the remote was standing on a key
		// that has just been taken off the screen, which leaves it on nothing.
		if (!tracks.length) {
			if (!sleeve.open) return;
			sleeve.hide();
			if (surface.isTv) return focusContent();
			return;
		}
		// a station somebody here pressed is a thing put on, and what is put on
		// opens; one merely found playing in the house is not
		const adopted = tracks.length === 1 && tracks[0].id < 0 && !tracks[0].url;
		const already = sleeve.onScreen !== null && sleeve.onScreen === tracks[0]?.release_id;
		if (!adopted && !already) sleeve.show();
	});

	$effect(() => {
		// a station has no catalogue id and no words of ours to look up
		void lyrics.load(track && track.id >= 0 ? track.id : null);
	});

	// A remote has one place to be, and when this opens that place is here: left
	// where it was, the first press goes to a shelf nobody can see any more.
	// Play is play whether it is drawn by the shared transport or by a station's
	// own single key — a record put on from another screen in the house opens
	// this, and a screen that opens with nothing focused reads as one that has
	// not noticed.
	$effect(() => {
		if (!sleeve.open || !surface.isTv) return;
		queueMicrotask(() => focusFirst('[data-control="toggle"]'));
	});

	$effect(() =>
		onBack(() => {
			if (!sleeve.open) return false;
			sleeve.hide();
			return true;
		})
	);

	// the library is still behind this, and a page that scrolls behind a screen
	// filling the screen is a scrollbar with nothing to say
	$effect(() => {
		if (!sleeve.open) return;
		const had = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		return () => {
			document.body.style.overflow = had;
		};
	});

	// Ten feet away the record stands on the left and the right is either the
	// words or what comes next. The words are chosen for a song that has them
	// timed, the rest when it has none; a song with no words at all has no tab
	// for them, rather than one that opens onto an apology.
	const worded = $derived(lyrics.timed || Boolean(lyrics.words?.plain));
	let pane = $state<'words' | 'queue'>('queue');
	$effect(() => {
		if (lyrics.loading) return;
		pane = lyrics.timed ? 'words' : 'queue';
	});

	// what the file is, said once and plainly: how a record was ripped is part of
	// why it is here rather than on a streaming service
	const fidelity = $derived.by(() => {
		if (!track?.codec) return '';
		const channels = track.channels ?? 0;
		const layout = channels > 2 ? t('sleeve.channels', { n: formatNumber(channels) }) : '';
		return [track.codec.toUpperCase(), layout].filter(Boolean).join(' · ');
	});
</script>

{#snippet words()}<Words {elapsed} {seek} />{/snippet}

{#if sleeve.open && track}
	<div class="sleeve" class:tv={surface.isTv} data-holds-remote>
		{#if track.cover_url}
			<div class="wash" style:background-image={cssUrl(art(track.cover_url, 500))}></div>
		{/if}

		<header>
			<Press tone="key" onclick={shrink} label={t('sleeve.collapse')}>
				<Icon name="down" size={18} /> <span class="word">{t('sleeve.collapse')}</span>
			</Press>
			<Press tone="key" onclick={shut} label={t('common.close')}><Icon name="close" size={18} /></Press>
		</header>

		{#if station}
			<div class="body dial">
				<section class="mark">
					{#if station.cover_url}
						<img class="logo" src={art(station.cover_url, 1000)} alt="" />
					{:else}
						<div class="logo blank"></div>
					{/if}
					<h1>{dial}</h1>
					{#if onAir}
						<p class="onair">{onAir}</p>
					{:else}
						<p class="onair quiet">{t('radio.live')}</p>
					{/if}

				</section>
			</div>
		{:else if surface.isTv}
		<div class="body turntable">
			<Turntable
				cover={track.cover_url}
				title={album}
				by={artist}
				quiet={fidelity}
				songs={queue.tracks}
				at={queue.index}
				{going}
				onpick={(i) => queue.jump(i)}
				instead={pane === 'words' && worded ? words : undefined}
			>
				{#snippet tabs()}
					{#if worded}
						<Press tone="pill" on={pane === 'words'} onclick={() => (pane = 'words')}>{t('sleeve.lyrics')}</Press>
					{/if}
					<Press tone="pill" on={pane === 'queue'} onclick={() => (pane = 'queue')}>{t('sleeve.upNext')}</Press>
				{/snippet}
			</Turntable>
		</div>
		{:else}
		<div class="body">
			<Record
				tracks={queue.tracks}
				cover={track.cover_url}
				{album}
				{artist}
				releaseId={track.release_id}
				{fidelity}
				playing={queue.index}
				{going}
				onplay={(i) => queue.jump(i)}
			/>
		</div>
		{/if}
	</div>
{/if}

<style>
	.sleeve {
		position: fixed;
		inset: 0;
		/* under the sections, which stand on every screen: a record filling the
		   screen is still a place you are in, and the list of places does not go
		   away for it. A film does — a film takes the screen from everything. */
		z-index: 19;
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		background: var(--bg);
		overflow: hidden;
	}
	/* the sleeve itself is the background, the way a poster is behind a film:
	   blown up, blurred and dimmed until it is a colour rather than a picture */
	.wash {
		position: absolute;
		inset: -10%;
		background-size: cover;
		background-position: center;
		filter: blur(80px) saturate(1.25);
		opacity: 0.34;
		pointer-events: none;
	}
	header,
	.body {
		position: relative;
	}
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.7rem 1.2rem;
		font-size: var(--fs-xl);
		color: color-mix(in srgb, var(--bright, var(--text)) 75%, transparent);
	}
	/* The record and what else is on it down one side, the words down the other.
	   The sleeve used to give half the screen to the picture and make the track
	   list and the words take turns behind a pair of tabs — so the words, which
	   are the half a person actually reads while a song plays, were the half
	   they had to ask for. */
	.body {
		display: grid;
		/* One column: the record across the top, its songs under it. The words
		   used to stand in a column beside the songs, which gave each of them
		   half a screen and neither of them enough — a title cut mid-word on one
		   side, a line of a song cut on the other. They are a screen of their
		   own now, and the songs have the width. */
		grid-template-columns: minmax(0, 62rem);
		grid-template-rows: auto minmax(0, 1fr);
		justify-content: center;
		row-gap: 1.2rem;
		/* the last line is room for the bar, which lies over this screen */
		padding: 0 2.5rem 5.5rem;
		min-height: 0;
		/* the record and its songs scroll together: the list used to scroll
		   inside its own box, which is a box the page cannot see and the remote
		   cannot push */
		overflow-y: auto;
		scrollbar-width: none;
	}

	/* A station, which is one thing on a screen rather than four. Its mark is set
	   on the same ground the shelf gives it, so the tile a person pressed and the
	   picture they are looking at are recognisably the same thing. */
	.body.dial {
		grid-template-columns: minmax(0, 34rem);
		grid-template-rows: minmax(0, 1fr);
		place-content: center;
		place-items: center;
	}
	.mark {
		display: grid;
		justify-items: center;
		gap: 1.1rem;
		text-align: center;
	}
	.logo {
		width: 15rem;
		aspect-ratio: 1;
		object-fit: contain;
		background: var(--logo-ground);
		padding: 12%;
		box-sizing: border-box;
		border-radius: 16px;
		box-shadow: var(--shadow-xl);
	}
	.logo.blank {
		background: color-mix(in srgb, var(--bright, var(--text)) 8%, transparent);
	}
	.onair {
		margin: 0;
		font-size: var(--fs-xl);
		color: color-mix(in srgb, var(--bright, var(--text)) 78%, transparent);
	}
	.onair.quiet {
		color: var(--muted);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		font-size: var(--fs-m);
	}
	.sleeve.tv .logo {
		width: 11rem;
	}
				
	/* Ten feet away, on the 960×540 the box reports at twice the density: the
	   same record as the desktop shows, in the same two columns, at measures
	   that fit what the page is actually given. Nothing here is a different
	   layout — only a smaller one. */
	/* the column the sections keep, kept here too */
	.sleeve.tv {
		padding-left: calc(var(--rail-w, 11rem) + 1rem);
	}
	.sleeve.tv .body {
		/* the record, and its songs across the width under it */
		grid-template-columns: minmax(0, 46rem);
		row-gap: 0.8rem;
		padding: 0 2rem 5.2rem;
	}
	.sleeve.tv .turntable {
		grid-template-columns: minmax(0, 57rem);
		grid-template-rows: minmax(0, 1fr);
	}
	/* One hand, one column: the sleeve above, the songs or the words below it,
	   and the keys where the thumb already is. */
	@media (max-width: 900px) {
		.body {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto minmax(0, 1fr);
			gap: 1rem;
			padding: 0 1rem 1rem;
		}
		.word {
			display: none;
		}
	}
</style>
