<script lang="ts">
	// The bar that says what is playing. It lives in the frame rather than on the
	// music page, because a record goes on and then you walk away from the page
	// that started it.

	import { cast } from '$lib/keep/cast.svelte';
	import { json, request } from '$lib/kit';
	import Outputs from '$lib/parts/Outputs.svelte';
	import PlayerBar from '$lib/parts/PlayerBar.svelte';
	import { hasEngine, queue } from '$lib/keep/queue.svelte';
	import Sleeve from '$lib/screens/Sleeve.svelte';
	import { sleeve } from '$lib/keep/sleeve.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { onBox } from '$lib/tv/bridge';
	import { Crossfade } from '$lib/keep/crossfade';

	/** Two elements, not one. A song used to end, and only THEN was the next
	 *  address handed to the same element — so the record stopped dead, the
	 *  browser went off to fetch the next file, and it started from silence.
	 *  Two decks let the one that follows be loaded and brought up while the one
	 *  playing is still going, which is what a fade between songs is. */
	let deckA = $state<HTMLAudioElement | null>(null);
	let deckB = $state<HTMLAudioElement | null>(null);
	let frontIsA = $state(true);
	const audio = $derived(frontIsA ? deckA : deckB);
	const spare = $derived(frontIsA ? deckB : deckA);
	let handing = $state(false);
	let elapsed = $state(0);

	/** How long the two overlap. Long enough to be a fade rather than a dip,
	 *  short enough that a three-minute song is still that song. */
	const FADE = 5;

	const track = $derived(queue.current);
	// A cast device can briefly report the song it is moving to before its queue
	// index reaches the page. Do not let that transient report paint the next
	// album on Home; for library tracks the queue is the selected source of truth.
	const remoteTrack = $derived(Boolean(
		cast.casting && track && (track.url || cast.trackId === track.id)
	));

	// the bar lies across the bottom of the page, so the page has to know: a
	// shelf that scrolls its last row under it is a row nobody can reach
	$effect(() => {
		document.documentElement.classList.toggle('playing', Boolean(track));
		return () => document.documentElement.classList.remove('playing');
	});
	const total = $derived(cast.casting ? cast.duration || (track?.duration_s ?? 0) : (track?.duration_s ?? 0));
	const going = $derived(cast.casting ? cast.playing : queue.playing);

	/** The television's own player rather than the page's.
	 *
	 *  A WebView decodes a 5.1 file and hands HDMI two channels, so a record put
	 *  on from the sofa reached the amplifier as stereo whatever the file held —
	 *  which is what the receiver said it was getting. The box's engine decodes
	 *  it with every channel, or passes it through to the receiver to decode.
	 *  The film player has driven it all along; music never asked. */
	const onEngine = $derived(
		!cast.casting && surface.isTv && hasEngine()
	);
	const fade = new Crossfade((active) => { handing = active; });
	$effect(() => {
		const decks = [audio, spare];
		const enabled = queue.playing && !cast.casting && !onEngine;
		const song = queue.current;
		if (!enabled || !song) fade.cancel();
		return () => {
			fade.cancel();
			const src = queue.src ? new URL(queue.src, location.href).href : '';
			for (const deck of decks) {
				if (deck && (!queue.playing || cast.casting || onEngine || deck !== audio || deck.src !== src))
					deck.pause();
			}
		};
	});

	// a new track means a new file; the element is told to play only when the
	// queue says it should be, so pausing survives moving to the next song
	$effect(() => {
		const src = queue.src;
		if (cast.casting || onEngine || !audio || !src) return;
		// the deck that was brought up under the last one is already playing this
		// song, some way into it; handing it the address again would start it over
		const at = queue.startAt;
		const changed = audio.src !== new URL(src, location.href).href;
		if (changed) audio.src = src;
		queue.startAt = 0;
		if (changed || at) elapsed = at;
		if (at) audio.currentTime = at;
		if (queue.playing) ask(audio);
	});

	/** Only the deck in front drives the needle and the end of the song; the one
	 *  coming up under it is playing too, and would run the clock backwards. */
	function onTick(event: Event, mine: boolean) {
		if (!mine) return;
		const el = event.currentTarget as HTMLAudioElement;
		elapsed = el.currentTime;
		queue.position = elapsed;
		if (Math.abs(elapsed - told) > 15) keep();
		const left = (el.duration || 0) - el.currentTime;
		if (Number.isFinite(el.duration) && el.duration > FADE && left <= FADE && queue.playing) {
			crossfade();
		}
	}

	/** The last song of a queue, or one the fade never caught — a station has no
	 *  end to run into at all. Told here, where the server reads it as finished
	 *  and forgets it: a record played through is not one to carry on with.
	 *
	 *  Not while a hand-over is running. The fade starts FADE seconds from the
	 *  end and takes FADE seconds, so the song underneath reaches its own end
	 *  mid-ramp — and answering that by moving the queue on left the ramp to
	 *  move it on again, which skipped the song that had just been faded in. */
	function onEnd() {
		if (handing) return;
		keep();
		queue.next();
	}

	/** Bring one deck down and the other up over FADE seconds, then swap them.
	 *  Volume rather than the Web Audio graph: the graph would want the files to
	 *  be CORS-readable and buys nothing a linear ramp does not already give. */
	function crossfade() {
		const going = audio;
		const coming = spare;
		const next = queue.nextSrc;
		if (!going || !coming || !next || handing) return;
		const song = queue.current;
		const index = queue.index;
		fade.start(going, coming, next, FADE, ask,
			() => queue.playing && !cast.casting && !onEngine && queue.current === song
				&& queue.index === index && queue.nextSrc === next,
			() => {
			// the deck that came up IS the next song, so the queue is told where it
			// already is rather than asked to start it
			frontIsA = !frontIsA;
			keep();
			queue.next();
		});
	}

	/** Asking an element to play in the same breath as handing it a new address
	 *  is refused by the load itself — "interrupted by a new load request" — and
	 *  a refusal taken at face value left a station chosen, loaded and silent,
	 *  with the remote sitting on a play button somebody had already pressed.
	 *  The element says when it is ready; that is when it is asked again. */
	const requests = new WeakMap<HTMLAudioElement, number>();
	function ask(el: HTMLAudioElement, valid = () => queue.playing && !cast.casting && !onEngine) {
		const generation = (requests.get(el) ?? 0) + 1;
		requests.set(el, generation);
		const src = el.src;
		const mine = () => requests.get(el) === generation && el.src === src;
		const current = () => mine() && valid();
		el.play().then(() => { if (mine() && !valid()) el.pause(); }).catch(() => {
			if (!current()) return;
			el.addEventListener(
				'canplay',
				() => {
					if (current()) el.play().then(() => { if (mine() && !valid()) el.pause(); })
						.catch(() => { if (current()) queue.playing = false; });
				},
				{ once: true }
			);
		});
	}

	// a device the bar is not itself driving still moves the needle
	$effect(() => {
		if (cast.casting) elapsed = cast.position;
	});

	$effect(() => {
		const song = queue.current;
		if (!onEngine || !song) return;
		// already going: the page came back to a box that never stopped
		if (queue.attached) {
			queue.attached = false;
			elapsed = queue.position;
			return;
		}
		const at = queue.startAt;
		queue.startAt = 0;
		elapsed = at;
		onBox((box) => box.describe?.(song.title, song.artist, song.album, song.cover_url ?? ''));
		// a station's bytes are not ours, and the engine opens nothing that is not
		// this origin's: every station goes through the relay, https or not
		if (song.url) {
			const relay = new URL(`/api/radio/stream?u=${encodeURIComponent(song.url)}`, location.origin).href;
			onBox((box) => box.play(relay, 0, '', '', '', 0));
			return;
		}
		void handOver(song.id, at);
	});

	/** The engine is not the page and carries none of its session: it opens the
	 *  file itself, holding only a link, so the bytes have to be reachable by
	 *  something holding only a link. The film player has asked for this ticket
	 *  since the beginning; music handed over a bare URL and the box was turned
	 *  away at the door with a 401. */
	async function handOver(id: number, at: number) {
		const pass = await request<{ prefix: string; ticket: string }>(
			`/api/play/track/${id}/ticket`
		);
		// the record may have moved on while the door was being asked
		if (!pass || queue.current?.id !== id) return;
		onBox((box) =>
			box.play(`${location.origin}${pass.prefix}stream?ticket=${encodeURIComponent(pass.ticket)}`, at, '', '', '', 0)
		);
	}

	// the engine is asked how it is doing rather than telling us: it lives on the
	// other side of a bridge that carries answers, not events
	$effect(() => {
		if (!onEngine) return;
		// The engine goes on saying it has ended for as long as nothing new is
		// playing, so the end is acted on once, where it begins.
		let ended = false;
		const beat = setInterval(() => {
			const said = onBox((box) => box.state());
			if (!said) return;
			const now = JSON.parse(said) as {
				position?: number;
				playing?: boolean;
				ended?: boolean;
			};
			elapsed = now.position ?? 0;
			queue.position = elapsed;
			queue.playing = Boolean(now.playing);
			if (Math.abs(elapsed - told) > 15) keep();
			if (now.ended && !ended) {
				keep();
				queue.next();
			}
			ended = Boolean(now.ended);
		}, 400);
		return () => clearInterval(beat);
	});

	/** Where the record was left, told to the server rather than kept here — a
	 *  record is put on in one room and carried on with in another, which is the
	 *  whole reason any of this is on the server. Sent on the minute rather than
	 *  on every tick: the element reports four times a second. */
	let told = 0;
	function keep(closing = false) {
		const song = queue.current;
		if (!song || song.live || song.id <= 0 || elapsed <= 0) return;
		told = elapsed;
		void request(
			'/api/progress',
			{
				...json({
					kind: 'track',
					item_id: song.id,
					position_s: elapsed,
					duration_s: song.duration_s,
					surface: surface.current
				}),
				keepalive: closing
			}
		);
	}

	// A song is heard once it has had half its length or four minutes, the rule
	// scrobbling has always used; once each time it is put on, however much of
	// it is sought back over.
	let heardFor = -1;
	$effect(() => {
		const song = queue.current;
		if (!song || song.live || song.id <= 0 || !song.release_id || !song.artist_id) return;
		if (elapsed <= 1) {
			heardFor = -1;
			return;
		}
		if (heardFor === song.id || elapsed < Math.min((song.duration_s ?? 480) / 2, 240)) return;
		heardFor = song.id;
		void request(
			'/api/music/plays',
			json({ track_id: song.id, release_id: song.release_id, artist_id: song.artist_id })
		);
	});

	// a page closed is a record left in the middle of a song
	$effect(() => {
		const onhide = () => keep(true);
		window.addEventListener('pagehide', onhide);
		return () => window.removeEventListener('pagehide', onhide);
	});

	$effect(() => {
		if (cast.casting || onEngine || !audio) return;
		if (queue.playing) ask(audio);
		else { audio.pause(); spare?.pause(); }
	});

	function toggle() {
		if (cast.casting) void cast.toggle();
		else if (onEngine) onBox((box) => box.toggle());
		else queue.playing = !queue.playing;
	}

	function forward() {
		if (cast.casting) void cast.next();
		else queue.next();
	}

	function back() {
		if (cast.casting) {
			void cast.previous();
			return;
		}
		// back a track, or back to the start of this one: what every transport
		// has done since tape, and what a thumb expects
		const at = onEngine ? elapsed : (audio?.currentTime ?? 0);
		if (at > 3) {
			if (onEngine) onBox((box) => box.seek(0));
			else if (audio) audio.currentTime = 0;
		} else if (queue.index > 0) queue.jump(queue.index - 1);
	}

	function shut() {
		void cast.silence();
	}

	function seek(to: number) {
		if (onEngine) onBox((box) => box.seek(to));
		else if (audio) audio.currentTime = to;
		// said here as well as waited for: a line of lyrics pressed on the full
		// screen must light up on the press, not on the element's next tick
		elapsed = to;
	}

</script>

{#if track}
	<!-- The one bar every player uses. It stands over whatever screen is
	     underneath and is reachable from it: the keys for the song that is
	     playing are not something a screen may lock away. -->
	{#if !cast.casting && !onEngine}
		<audio
			bind:this={deckA}
			ontimeupdate={(e) => onTick(e, frontIsA)}
			onended={() => frontIsA && onEnd()}
			onpause={() => frontIsA && keep()}
			onerror={() => frontIsA && (queue.playing = false)}
		></audio>
		<audio
			bind:this={deckB}
			ontimeupdate={(e) => onTick(e, !frontIsA)}
			onended={() => !frontIsA && onEnd()}
			onpause={() => !frontIsA && keep()}
			onerror={() => !frontIsA && (queue.playing = false)}
		></audio>
	{/if}

	<div class="stays" data-stays>
		{#snippet alsoHere()}
			<Outputs />
		{/snippet}
		<PlayerBar
			art={track.cover_url}
			title={remoteTrack && cast.title ? cast.title : track.title}
			subtitle={[
				remoteTrack && cast.artist ? cast.artist : track.artist,
				remoteTrack && cast.album ? cast.album : track.album
			]
				.filter(Boolean)
				.join(' · ')}
			position={elapsed}
			{total}
			{going}
			{toggle}
			{seek}
			prev={back}
			next={forward}
			hasNext={queue.hasNext || cast.casting}
			seekable={!cast.casting}
			onopen={() => sleeve.show()}
			onclose={shut}
			extras={alsoHere}
		/>
	</div>
{/if}

<!-- outside the bar, and mounted whether or not anything is on: the screen has
     to be there to know that a record has just been put on -->
<Sleeve {elapsed} {total} {going} {toggle} {forward} {back} {seek} {shut} />

<style>
	/* the bar is fixed, so this wrapper is only a handle for the arrows to find
	   it by from whatever is standing over the screen */
	.stays {
		display: contents;
	}
</style>
