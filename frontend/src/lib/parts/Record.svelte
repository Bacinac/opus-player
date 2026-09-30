<script lang="ts">
	// A record, wherever it is looked at.
	//
	// There were two of these: the one a person reaches by walking an artist's
	// shelf, and the one that opened when a record went on. They showed the same
	// twelve songs in two different arrangements, so putting a record on changed
	// what the screen was, which is not what pressing play means. This is the
	// one, and what is playing is said by the bar along the bottom — the thing
	// that is on every screen anyway.

	import { Icon } from '$lib/kit';
	import { MediaHead } from '$lib/opus';
	import { art } from '$lib/ask/art';
	import { about } from '$lib/keep/about.svelte';
	import { musicGenreName } from '$lib/say/genre';
	import { favorites } from '$lib/keep/favorites.svelte';
	import { watching } from '$lib/keep/watching.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { count } from '$lib/say/count';
	import { duration, t } from '$lib/i18n';
	import type { QueueTrack } from '$lib/keep/queue.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import Turntable from '$lib/tvui/Turntable.svelte';
	import Words from '$lib/parts/Words.svelte';
	import { albumWords, LyricsState } from '$lib/keep/lyrics.svelte';
	import { queue } from '$lib/keep/queue.svelte';
	import { focusWaiting } from '$lib/tv/spatial.svelte';

	let {
		tracks,
		cover = null,
		album = '',
		artist = '',
		releaseId = null,
		year = '',
		fidelity = '',
		playing = -1,
		going = false,
		onplay,
	}: {
		tracks: QueueTrack[];
		cover?: string | null;
		album?: string;
		artist?: string;
		releaseId?: number | null;
		year?: string;
		/** what the file is — FLAC, and how many channels of it */
		fidelity?: string;
		/** which song of these is on, if one of them is */
		playing?: number;
		going?: boolean;
		/** a song of this record, from a second in if the words say where */
		onplay: (index: number, at?: number) => void;
	} = $props();

	const told = $derived(about.told(releaseId));
	/** What a record is, in one line: whose it is, when it is from, what kind of
	 *  music, how many songs, how long they run and who put it out. Said the same
	 *  way whether the record is playing or merely being looked at. */
	const seconds = $derived(tracks.reduce((sum, one) => sum + (one.duration_s ?? 0), 0));
	const songs = $derived(tracks.length ? count(tracks.length, 'songs').text : null);
	const running = $derived(seconds ? duration(seconds) : null);
	const line = $derived(
		[artist, year, told.genres[0] && musicGenreName(told.genres[0]), songs, running, told.label, fidelity].filter(Boolean).join(' · ')
	);

	$effect(() => {
		void about.ask(releaseId ?? undefined);
	});

	// The words to a song, on the record's own screen rather than only over the
	// bar: this one reads whichever song the remote is standing on, which is
	// usually not the song that is playing.
	const reading = new LyricsState();
	let showing = $state<'songs' | 'words'>('songs');
	let atSong = $state(0);

	// the marks beside the songs are asked for as the record opens, because they
	// are drawn before anything is pressed
	$effect(() => {
		void albumWords.ask(surface.isTv ? releaseId : null);
	});

	// and the words themselves only while somebody is reading them
	$effect(() => {
		if (showing !== 'words') return;
		void reading.load(tracks[atSong]?.id ?? null);
	});

	// a record put away takes its reading with it. Only the record is watched:
	// hanging this on what is playing would put the songs back every time the
	// record walked to its next track, with somebody reading the words
	$effect(() => {
		void releaseId;
		showing = 'songs';
		atSong = 0;
	});

	// the line being sung, but only when the song being read is the song that is
	// sounding — the words to the next track do not follow anybody's playback
	const elapsed = $derived(playing === atSong ? queue.position : 0);

	// the page that was there before this record went, and the ring with it
	$effect(() => (surface.isTv ? focusWaiting('.panel .go') : undefined));

	// A television is a household screen, not a signed-in person. Its list is
	// deliberately read-only for personal choices such as favourites.
	$effect(() => {
		if (watching.person && !surface.isTv) void favorites.ask();
	});
	const mayFavorite = $derived(Boolean(watching.person) && !surface.isTv && favorites.ready);

	let list = $state<HTMLElement | null>(null);
	// what is playing is brought into view when it changes on its own — a record
	// walks to its next song while somebody is looking at the list
	$effect(() => {
		if (!list || playing < 0) return;
		list
			.querySelector<HTMLElement>(`[data-song="${playing}"]`)
			?.scrollIntoView({ block: 'nearest' });
	});
</script>

{#if surface.isTv}
	<Turntable
		{cover}
		title={album}
		by={artist}
		quiet={[year, songs, running].filter(Boolean).join(' · ')}
		songs={tracks}
		at={playing}
		{going}
		words={albumWords.releaseId === releaseId ? albumWords.have : undefined}
		onpick={onplay}
		onat={(i) => (atSong = i)}
		instead={showing === 'words' ? wordsOf : undefined}
	>
		{#snippet keys()}
			<Press tone="go" onclick={() => onplay(0)}>{t('card.play')}</Press>
		{/snippet}
		{#snippet tabs()}
			<Press tone="pill" on={showing === 'songs'} onclick={() => (showing = 'songs')}>
				{t('music.songs')}
			</Press>
			<Press tone="pill" on={showing === 'words'} onclick={() => (showing = 'words')}>
				{t('sleeve.lyrics')}
			</Press>
			<span class="reading">{tracks[atSong]?.title ?? ''}</span>
		{/snippet}
	</Turntable>
	<!-- a line of a song is a place in it: pressing one plays this song from
	     there, whether or not it was the song that was on -->
	{#snippet wordsOf()}
		<Words {reading} {elapsed} seek={(to) => onplay(atSong, to)} />
	{/snippet}
{:else}
<MediaHead
	title={album}
	subtitle={line}
	overview={told.description}
	poster={cover ? art(cover, 500) : null}
	square
/>

<ol class="songs" bind:this={list}>
	{#each tracks as song, i (song.id)}
		<li>
			<div class="song">
				<button class="play" class:on={i === playing} data-song={i} onclick={() => onplay(i)}>
					<span class="num">{i === playing && going ? '♪' : song.position}</span>
					<span class="name">{song.title}</span>
					<span class="len">{duration(song.duration_s)}</span>
				</button>
				{#if mayFavorite}
					<button
						class="favorite"
						class:held={favorites.has(song.id)}
						disabled={favorites.busy(song.id)}
						title={favorites.has(song.id) ? t('music.favoriteRemove') : t('music.favoriteAdd')}
						aria-label={favorites.has(song.id) ? t('music.favoriteRemove') : t('music.favoriteAdd')}
						onclick={() => favorites.toggle(song.id)}
					>
						<Icon name="heart" size={16} />
					</button>
				{/if}
			</div>
		</li>
	{/each}
</ol>

{/if}

{#if !tracks.length}
	<p class="quiet">{t('common.loading')}</p>
{/if}

<style>
	/* Two columns, and the numbers run DOWN the first before starting the
	   second: 1–6 on the left, 7–12 on the right. Laid across instead — 1 and 2
	   side by side — the eye has to zigzag to read a tracklist in order, which
	   is the one order a tracklist has. CSS columns rather than a grid, because
	   filling a column before moving on is what they are for.

	   Each column is capped: across the full page width the time would sit an
	   arm's length from the title it belongs to. */
	.songs {
		column-count: 2;
		column-gap: 3rem;
		max-width: 72rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.songs li {
		break-inside: avoid;
	}
	/* a narrow window has no room for two, and a television reads one list */
	@media (max-width: 60rem) {
		.songs {
			column-count: 1;
			max-width: 34rem;
		}
	}
	.song {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
	}
	.songs .play {
		display: grid;
		/* the number, the name as wide as it needs, the time beside it */
		grid-template-columns: 1.6rem minmax(0, 1fr) auto;
		align-items: center;
		gap: 0.7rem;
		width: 100%;
		border: none;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		padding: 0.55rem 0.7rem;
		border-radius: 8px;
		cursor: pointer;
	}
	/* The ring the shared layer draws stays. It was cancelled here and replaced
	   with a 12% wash — FAINTER at rest than the track already playing below,
	   so the song you were pointing at read as less chosen than the one that
	   was already on. */
	.songs .play:hover {
		background: color-mix(in srgb, currentColor 12%, transparent);
	}
	.songs .play.on {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
	}
	.num,
	.len {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
		font-size: 0.9em;
	}
	.songs .play.on .num {
		color: inherit;
	}
	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.favorite {
		display: grid;
		place-items: center;
		width: 2.25rem;
		height: 2.25rem;
		border: none;
		border-radius: 8px;
		background: transparent;
		color: var(--muted);
		cursor: pointer;
	}
	.favorite:hover:not(:disabled),
	.favorite:focus-visible {
		background: color-mix(in srgb, var(--accent) 14%, transparent);
		color: var(--accent);
	}
	.favorite.held {
		color: var(--accent);
	}
	.favorite:disabled {
		cursor: default;
		opacity: 0.55;
	}
	.quiet {
		color: var(--muted);
	}
	/* which song is being read, beside the choice of what this side shows */
	.reading {
		align-self: center;
		margin-left: 0.4rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--muted);
	}
</style>
