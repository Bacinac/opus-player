<script lang="ts">
	// Watching something.
	//
	// The transport is drawn here rather than left to the video element. A
	// fragmented stream carries no duration, so the element believes the film is
	// as long as the part it has received — which is why its clock and its bar
	// read as nonsense. The real length comes from the file; where you are is
	// where the stream was started plus how far into it the element has got, and
	// seeking restarts the stream at the new place.

	import { art } from '$lib/ask/art';
	import { t, formatNumber, formatTime, plural } from '$lib/i18n';
	import Press from '$lib/tvui/Press.svelte';
	import { episodeLabel } from '$lib/say/episode';
	import Choose from '$lib/tvui/Choose.svelte';
	import PlayerBar from '$lib/parts/PlayerBar.svelte';
	import Captions from '$lib/parts/Captions.svelte';
	import FilmInfo from '$lib/parts/FilmInfo.svelte';
	import { Icon, json, request, toasts, withLang } from '$lib/kit';
	import { onBox } from '$lib/tv/bridge';
	import { FilmEngine } from '$lib/tv/filmEngine.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { asked, decodes, here } from '$lib/ask/ability';
	import { hasEngine, queue } from '$lib/keep/queue.svelte';
	import type { Card, Plan } from '$lib/keep/types';
	import { film, type FilmOnTv } from '$lib/keep/film.svelte';
	import { televisions, tvFilm, type Box } from '$lib/keep/tvFilm.svelte';
	import { languageOf, offeredSubtitles, soundName, subtitleName } from '$lib/say/tracks';
	import { FilmRemote } from '$lib/tv/filmRemote.svelte';
	import { untrack } from 'svelte';

	let { card, onclose }: { card: Card; onclose: () => void } = $props();
	const lent = $derived(film.lentFor(card));

	let plan = $state<Plan | null>(null);
	let problem = $state('');
	let src = $state('');
	let video = $state<HTMLVideoElement | null>(null);
	// the track whose cues Captions is painting; `applyTracks` names it
	let subsTrack = $state<TextTrack | null>(null);
	let chosenSub = $state<number | null>(null);
	let chosenAudio = $state(0);
	let showInfo = $state(false);
	let efficient = $state<boolean | null>(null);
	let stage = $state<HTMLDivElement | null>(null);
	const engine = new FilmEngine((detail) => (problem = detail));
	let full = $state(false);
	// in full screen the picture is the whole point; the transport comes back
	// when a hand moves and leaves again when it stops
	let idle = $state(false);
	let idleTimer: ReturnType<typeof setTimeout> | null = null;

	function stir() {
		idle = false;
		if (idleTimer) clearTimeout(idleTimer);
		if (full) idleTimer = setTimeout(() => (idle = true), 2500);
	}
	// what the picture is being sized for, kept so the panel can say it rather
	// than leaving the number to be guessed at
	let panel = $state({ w: 0, h: 0, ratio: 1 });

	// where the current stream was started from; the element's own clock counts
	// from there, not from the beginning of the film
	let offset = $state(0);
	let inStream = $state(0);
	let query = $state('');
	// A phone can hand the film to a Chromecast or an Apple TV, and the browser
	// gives that device the element's address and nothing else: no cookie goes
	// with it, so the address carries a ticket
	let pass = $state('');
	let castable = $state(false);
	let casting = $state(false);
	// our own televisions, which take the film whole — its sound, its subtitles,
	// its picture as the box can decode it — rather than the phone's stream of it
	let boxes = $state<Box[]>([]);
	if (!surface.isTv) void televisions().then((got) => (boxes = got));
	// a direct file cannot be started part-way by the server, so the seek waits
	// for the element to know its own length
	let pending = $state(0);

	// direct play could use the browser's own controls, and did — which meant the
	// subtitle menu and the details button existed in two modes out of three and
	// moved when the file changed. One transport, always, and seeking a direct
	// stream simply sets the element's clock instead of restarting anything.
	const native = $derived(plan?.mode === 'direct');
	const position = $derived(
		engine.on ? engine.from + engine.at : native ? inStream : offset + inStream
	);
	const total = $derived(
		engine.on && !engine.rebuilt && engine.length > 0 ? engine.length : (plan?.duration_s ?? 0)
	);
	// a paused film ends later by every minute it stays paused, so the clock is
	// read on a beat and not only when the position moves
	let now = $state(Date.now());
	$effect(() => {
		const beat = setInterval(() => (now = Date.now()), 15000);
		return () => clearInterval(beat);
	});
	const ends = $derived(total > 0 ? formatTime(new Date(now + (total - position) * 1000)) : '');

	// The closing credits are where an evening of a series goes on to the next
	// episode. A file the library found no credits in offers it for its last
	// half minute, which is about what a sitcom's run.
	const WITHOUT_CREDITS_S = 30;
	const creditsAt = $derived(
		plan?.credits_s ?? (total > WITHOUT_CREDITS_S ? total - WITHOUT_CREDITS_S : null)
	);
	const offerNext = $derived(Boolean(plan?.next) && creditsAt !== null && position >= creditsAt);
	const offerSkip = $derived(
		plan?.intro_s != null &&
			plan.intro_end_s != null &&
			position >= plan.intro_s &&
			position < plan.intro_end_s
	);

	function skipIntro() {
		if (plan?.intro_end_s != null) seekTo(plan.intro_end_s);
	}
	const seasonLeft = $derived(
		plan?.season_left == null
			? ''
			: plan.season_left === 0
				? t('play.seasonLast')
				: plural(plan.season_left, 'play.seasonLeft.one', 'play.seasonLeft.few', 'play.seasonLeft.many')
	);

	/** The next episode, over this one: this one is finished from where its
	 *  credits begin, and the next is put on by the screen the house uses for a
	 *  film asked for from anywhere — closed first, because that screen may be
	 *  this one. */
	function playNext() {
		const after = plan?.next;
		if (!after) return;
		// built before closing: the card is the opener's, and closing takes it
		const next: Card = {
			kind: 'episode',
			id: after.id,
			series_id: card.series_id,
			title: card.title,
			subtitle: episodeLabel(after.season_number, after),
			image: card.image,
			backdrop: card.backdrop,
			state: 'complete',
			overview: ''
		};
		const whose = lent;
		keepPosition(true);
		onclose();
		film.carryOn(next, whose);
	}

	async function toggleFull() {
		if (document.fullscreenElement) {
			await document.exitFullscreen();
		} else {
			await stage?.requestFullscreen();
		}
		full = Boolean(document.fullscreenElement);
		showInfo = showInfo && !full;
		stir();
	}

	async function arrange() {
		try {
			await settle();
		} catch (err) {
			problem = err instanceof Error ? err.message : String(err);
		}
	}

	/** Hand the film to the engine and get out of the way. The engine draws the
	 *  picture on a surface of its own, so leaving this page's transport behind it
	 *  would be a set of controls nobody can see operating a video nobody is
	 *  watching. Where you got to is reported by the wrapper, because this page is
	 *  in the background from the moment the engine starts. */
	async function handOver() {
		const taken = await engine.plan(card, chosenAudio, { failed: (detail: string) => (problem = detail) });
		if (!taken) return;
		chosenAudio = taken.audio;
		// A film is decoded by the Shield itself.  Tell the house to leave the
		// previous iFi/DAC source before the HDMI engine starts, otherwise the
		// receiver can keep the old record audible underneath the picture.
		if (surface.isTv) {
			await request('/api/tv/video', json({}), {
				failed: (detail: string) => (problem = detail)
			});
		}
		// the plan is published only when the engine takes the film in the same
		// breath: a plan standing on its own mounts the page's video element
		const at = await stoppedAt();
		// closed while the plan was being asked for: a film started now would play
		// behind a page that no longer exists, with nothing left to stop it
		if (gone) return;
		plan = taken.plan;
		// the box has one engine and a film is about to take it: a record left
		// running would be released under the bar that still says it is playing
		queue.clear();
		onBox((box) => box.describe?.(card.title, String(card.subtitle ?? ''), '', card.image ?? ''));
		if (engine.start(taken.plan, at)) engine.on = true;
	}

	async function settle() {
		if (hasEngine()) {
			await handOver();
			return;
		}
		const place = here();
		panel = { w: place.width, h: place.height, ratio: window.devicePixelRatio || 1 };
		const refused = { failed: (detail: string) => (problem = detail) };
		const [seen, ticket] = await Promise.all([
			request<Plan>(withLang(`/api/play/${card.kind}/${card.id}/plan?${asked(place)}`), {}, refused),
			request<{ prefix: string; ticket: string }>(`/api/play/${card.kind}/${card.id}/ticket`, {}, refused)
		]);
		if (!seen || !ticket) return;
		pass = `ticket=${encodeURIComponent(ticket.ticket)}`;
		const able = await decodes(place, seen.source.video_codec, seen.source.width, seen.source.height);
		efficient = able;
		query = asked(place, { canDecode: able, audio: chosenAudio });
		const settled = await request<Plan>(
			withLang(`/api/play/${card.kind}/${card.id}/plan?${query}`),
			{},
			refused
		);
		if (!settled) return;
		// the resume point is fetched before the plan is published: the video
		// element mounts the moment the plan exists, and an element that mounts
		// with an empty src is refused by the browser before a later assignment
		// can reach it
		const at = await stoppedAt();
		plan = settled;
		start(at);
		// what was put on says so, then gets out of the way. A picture that
		// begins under a bar nobody asked for is a bar; a picture that begins
		// with no word about what it is is a guess.
		remote.glance();
	}

	function start(at: number) {
		offset = at;
		inStream = 0;
		// a direct file is served whole and seeks in the element, so the stream
		// cannot be started elsewhere; the clock is set once the element knows
		// how long it is
		pending = native && at > 0 ? at : 0;
		src = `/api/play/${card.kind}/${card.id}/stream?${query}&t=${Math.floor(at)}&${pass}`;
	}

	$effect(() => {
		const sent = video?.remote;
		if (!sent || surface.isTv) return;
		let watching: number | null = null;
		const follow = () => {
			casting = sent.state !== 'disconnected';
			if (!casting && leaving) onclose();
		};
		sent
			.watchAvailability((there) => (castable = there))
			.then((id) => (watching = id))
			.catch((err: DOMException) => {
				// a desktop browser mirrors the film instead of listening for
				// devices, and only its own picker knows whether there are any
				if (err.name !== 'NotSupportedError') throw err;
				castable = true;
			});
		const events = ['connecting', 'connect', 'disconnect'];
		for (const event of events) sent.addEventListener(event, follow);
		return () => {
			for (const event of events) sent.removeEventListener(event, follow);
			if (watching !== null) void sent.cancelWatchAvailability(watching);
		};
	});

	// The film is playing through Chrome on another screen. That session belongs
	// to the browser and outlives this page — closing the page left the film
	// running on the television with nothing here to say so. Chrome's own dialog
	// is the one thing that ends it; the page goes once it has.
	let leaving = false;
	function leave() {
		if (!casting) {
			onclose();
			return;
		}
		leaving = true;
		void elsewhere();
	}

	function castTo() {
		if (boxes.length) remote.openMenu('cast');
		else void elsewhere();
	}

	async function sendTo(box: Box) {
		const at = position;
		keepPosition(true);
		if (await tvFilm.send(card, box, at)) onclose();
	}

	async function elsewhere() {
		try {
			await video?.remote.prompt();
		} catch (err) {
			const name = (err as DOMException).name;
			if (name === 'AbortError') return;
			toasts.error(name === 'NotFoundError' ? t('play.castNone') : (err as Error).message);
		}
	}

	/** Another language of the same film, from where you had got to. The whole
	 *  stream is rebuilt around the new track, so this is a seek that happens to
	 *  change the sound. */
	async function pickAudio(index: number) {
		const at = position;
		chosenAudio = index;
		query = query.replace(/audio=\d+/, `audio=${index}`);
		const made = await request<Plan>(withLang(`/api/play/${card.kind}/${card.id}/plan?${query}`));
		if (made) plan = made;
		start(at);
	}

	/** The next scene in the direction asked for, or nothing when the film was
	 *  released without any — most streaming rips are, most discs are not. */
	function chapterFrom(at: number, step: number): number | null {
		const marks = (plan?.chapters ?? []).map((c) => c.start_s).sort((a, b) => a - b);
		if (marks.length < 2) return null;
		if (step > 0) return marks.find((mark) => mark > at + 1) ?? null;
		// back means the start of this scene, and the one before it only if you
		// are already at the start — the way a disc remote has always behaved
		const past = marks.filter((mark) => mark < at - 3);
		return past.length ? past[past.length - 1] : 0;
	}

	function chapterAt(at: number): { number: number; title: string } | null {
		const marks = [...(plan?.chapters ?? [])].sort((a, b) => a.start_s - b.start_s);
		if (marks.length < 2) return null;
		let found = marks[0];
		for (const mark of marks) if (mark.start_s <= at + 0.5) found = mark;
		return { number: marks.indexOf(found) + 1, title: found.title };
	}

	function seekTo(to: number) {
		const at = Math.max(0, total ? Math.min(total, to) : to);
		if (engine.on && plan) {
			engine.seek(plan, at);
		} else if (native && video) {
			video.currentTime = at;
		} else {
			start(at);
		}
	}

	function toggle() {
		if (engine.on) {
			engine.toggle();
			return;
		}
		if (video?.paused) video.play();
		else video?.pause();
	}

	// the element's own flag is not something the page is told about changing
	let videoPaused = $state(true);
	const paused = $derived(engine.on ? !engine.playing : videoPaused);

	const remote = new FilmRemote({
		stage: () => stage,
		ready: () => plan !== null,
		position: () => position,
		seek: seekTo,
		toggle,
		onward: () => {
			if (offerSkip) {
				skipIntro();
				return true;
			}
			if (!offerNext) return false;
			playNext();
			return true;
		},
		scene: chapterFrom,
		hideInfo: () => {
			if (!showInfo) return false;
			showInfo = false;
			return true;
		},
		stir
	});

	/** The panel is here to be believed, so the numbers on it come from whoever
	 *  is playing. A browser's measure of the window is not the television. */
	function screenSize(): string {
		if (engine.on) {
			const place = here();
			if (place.width && place.height) return `${formatNumber(place.width)} × ${formatNumber(place.height)}`;
		}
		return `${formatNumber(panel.w)} × ${formatNumber(panel.h)}${panel.ratio !== 1 ? ` · ${formatNumber(panel.ratio)}×` : ''}`;
	}

	/** The tracks on the screen and the track that changes have to be one list,
	 *  so it comes from whoever is playing rather than from whoever asked. */
	function audioList() {
		return engine.on && !engine.rebuilt
			? engine.audio.map((a) => ({
					index: a.index,
					lang: a.lang,
					channels: a.channels,
					codec: a.codec,
					forced: false
				}))
			: (plan?.audio ?? []).map((a) => ({ ...a, forced: false }));
	}

	function subList() {
		return engine.on
			? engine.text.map((sub, at) => ({
					index: sub.index,
					lang: languageOf(sub.lang),
					label: sub.label,
					forced: false,
					number: at + 1
				}))
			: offered.map((sub, at) => ({ index: sub.id, lang: sub.lang, label: '', forced: sub.forced, number: at + 1 }));
	}

	function nowAudio(): number {
		return engine.on && !engine.rebuilt ? (engine.audio.find((a) => a.chosen)?.index ?? 0) : chosenAudio;
	}

	function nowSub(): number | null {
		return engine.on ? (engine.text.find((sub) => sub.chosen)?.index ?? null) : chosenSub;
	}

	function takeAudio(index: number) {
		if (engine.on && plan) {
			if (engine.rebuilt) chosenAudio = index;
			engine.chooseAudio(plan, index, position);
		} else pickAudio(index);
	}

	function takeSub(index: number | null) {
		if (engine.on) engine.chooseText(index);
		else pickSub(index);
	}

	function audioLabel(): string {
		const track = audioList().find((a) => a.index === nowAudio()) ?? audioList()[0];
		return track ? soundName(track) : '';
	}

	function subLabel(): string {
		const at = nowSub();
		if (at === null) return t('play.subtitlesOff');
		const sub = subList().find((entry) => entry.index === at);
		return sub ? subtitleName(sub) : '';
	}

	// Captured rather than bubbled: the ten-foot surface moves focus around the
	// whole page on the arrows, and while a film is up those keys are the film's.
	$effect(() => {
		window.addEventListener('keydown', remote.onkey, true);
		return () => window.removeEventListener('keydown', remote.onkey, true);
	});

	const offered = $derived(offeredSubtitles(plan?.subtitles ?? []));

	/** A <track> is inert until it is told to show, and the element holds its
	 *  tracks in the order the PLAN listed them — not the order of the menu,
	 *  which puts this house's languages first. Matching menu positions to
	 *  element positions is how choosing Croatian switched on English. The
	 *  chosen library index is mapped through the plan's own list, and the
	 *  modes are re-asserted on every tick rather than set once: the browser
	 *  switches tracks on by itself when their language matches a general
	 *  preference, and a seek swaps every track file for one rebased to the
	 *  new stream. */
	function applyTracks() {
		if (!video) return;
		const pos = plan?.subtitles.findIndex((s) => s.id === chosenSub) ?? -1;
		let chosen: TextTrack | null = null;
		Array.from(video.textTracks).forEach((track, i) => {
			// `hidden`, not `showing`: the cues are parsed and kept current but the
			// browser draws none of them, because Captions draws them over the
			// picture instead of into the element's black bar
			const mode: TextTrackMode = chosenSub !== null && i === pos ? 'hidden' : 'disabled';
			if (track.mode !== mode) track.mode = mode;
			if (mode === 'hidden') chosen = track;
		});
		if (subsTrack !== chosen) subsTrack = chosen;
	}

	function pickSub(index: number | null) {
		chosenSub = index;
		applyTracks();
	}

	/** Where this was left, if it was left anywhere. The server is asked rather
	 *  than the card trusted: the card may have been painted before somebody
	 *  watched another ten minutes of it in the kitchen. */
	async function stoppedAt(): Promise<number> {
		const sent = film.sentAt(card);
		if (sent !== null) return sent;
		const whose = lent ? `?${new URLSearchParams({ sent: lent, parent: String(card.series_id ?? '') })}` : '';
		const mark = await request<{ position_s: number }>(`/api/progress/${card.kind}/${card.id}${whose}`);
		return mark && mark.position_s > 10 ? mark.position_s : 0;
	}

	/** Where you got to, told to the server rather than kept here: the point of
	 *  keeping it at all is that the next screen is a different browser. */
	function keepPosition(closing = false) {
		if (!plan || !(position > 0)) return;
		void request(
			'/api/progress',
			{
				...json({
					kind: card.kind,
					item_id: card.id,
					position_s: position,
					duration_s: plan.duration_s,
					credits_s: plan.credits_s ?? null,
					surface: surface.current,
					parent_id: card.series_id ?? null,
					sent: lent
				}),
				keepalive: closing
			}
		);
	}

	// once per film: a sound or a language chosen while it plays must not start it again
	$effect(() => {
		untrack(arrange);
	});

	$effect(() => {
		if (!engine.on) return;
		const look = setInterval(() => {
			if (engine.look()) onclose();
		}, 500);
		return () => clearInterval(look);
	});

	/** Back on a remote means leave the film, not walk the page's history. The
	 *  wrapper asks here first and only navigates if nothing was watching. */
	$effect(() => {
		return onBack(() => {
			// Back takes away the topmost thing standing over the film, one at a
			// time. Only when nothing is standing over it does back mean leave.
			if (remote.menu) {
				remote.closeMenu();
				return true;
			}
			if (showInfo) {
				showInfo = false;
				return true;
			}
			if (remote.inBar) {
				remote.leaveBar();
				return true;
			}
			leave();
			return true;
		});
	});

	// subtitles step out from behind the bar for as long as it is up
	$effect(() => {
		if (!engine.on) return;
		engine.captionsUp(remote.inBar || remote.peek);
	});

	// letting go of the engine is part of closing, not something the page can
	// leave running behind itself
	let gone = false;
	// the picture hides the page and the ring falls off whatever opened it;
	// closing gives it back rather than leaving the frame to land somewhere else
	const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
	$effect(() => () => {
		gone = true;
		if (engine.on) engine.stop();
		requestAnimationFrame(() => {
			if (opener?.isConnected && opener !== document.body) opener.focus({ preventScroll: true });
		});
	});

	// the house hears what this film is doing and can reach its keys, for as
	// long as the box's own engine is playing it
	$effect(() => {
		if (!engine.on) return;
		// one engine, one film: whichever screen was playing the last one lets go.
		// Untracked, or writing film.current below would run this again and stop
		// the film that just started.
		untrack(() => film.current)?.stop();
		const mine: FilmOnTv = {
			kind: card.kind,
			id: card.id,
			title: card.title,
			subtitle: String(card.subtitle ?? ''),
			cover: card.image ?? null,
			position: () => position,
			duration: () => total,
			seek: seekTo,
			playing: () => engine.playing,
			toggle,
			step: (by) => {
				const mark = chapterFrom(position, by);
				if (mark !== null) seekTo(mark);
			},
			episode: playNext,
			stop: onclose
		};
		film.current = mine;
		return () => {
			if (film.current === mine) film.current = null;
		};
	});

	$effect(() => {
		if (!engine.on) return;
		return engine.uncover(stage);
	});

	// often enough that closing the lid loses seconds rather than minutes, and
	// once more on the way out because that is the position that matters
	$effect(() => {
		const mark = setInterval(() => keepPosition(), 15000);
		// a tab closed or put away is a film left where it stood, and the
		// component is not destroyed on the way out of a page
		const away = () => keepPosition(true);
		const hidden = () => document.visibilityState === 'hidden' && keepPosition(true);
		window.addEventListener('pagehide', away);
		document.addEventListener('visibilitychange', hidden);
		film.screens += 1;
		return () => {
			clearInterval(mark);
			window.removeEventListener('pagehide', away);
			document.removeEventListener('visibilitychange', hidden);
			film.screens -= 1;
			keepPosition(true);
		};
	});

	// the library is still behind this, and a page that scrolls behind a picture
	// that fills the screen is a scrollbar with nothing to say
	$effect(() => {
		const had = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		return () => {
			document.body.style.overflow = had;
		};
	});
</script>

<svelte:document onfullscreenchange={() => { full = Boolean(document.fullscreenElement); stir(); }} />

<!-- the whole surface listens for a hand so the chrome can get out of the way
     in full screen; it is a region, not a control -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
	class="stage"
	class:full
	class:idle={full && idle}
	class:tv={surface.isTv}
	class:engine={engine.on}
	bind:this={stage}
	onmousemove={stir}
	onkeydown={stir}
	role="region"
	aria-label={plan?.title ?? ''}
	tabindex="-1"
>
	{#if !surface.isTv}
		<button
			class="close"
			inert={remote.menu !== null}
			onclick={leave}
			aria-label={t('common.close')}><Icon name="close" size={18} /></button>
	{/if}

	{#if problem}
		<p class="problem">{problem}</p>
	{:else if plan}
		<!-- the chrome, which in full screen is only there while a hand is moving -->
		<!-- the tracks below are the captions; the rule cannot see them because
		     they are produced by an each block -->
		<!-- svelte-ignore a11y_media_has_caption -->
		{#if !engine.on}
		<video
			bind:this={video}
			{src}
			autoplay
			playsinline
			controls={false}
			controlslist="noremoteplayback"
			onplay={() => (videoPaused = false)}
			onpause={() => (videoPaused = true)}
			onerror={() => {
				const refused = video?.error;
				if (refused?.message) console.error('the browser refused the stream:', refused.message);
				problem = t('play.refused', { code: refused ? formatNumber(refused.code) : '—' });
			}}
			ontimeupdate={() => {
				inStream = video?.currentTime ?? 0;
				applyTracks();
			}}
			onloadedmetadata={() => {
				applyTracks();
				if (pending > 0 && video) {
					video.currentTime = pending;
					pending = 0;
				}
			}}
		>
			<!-- cues carry the film's own time; a stream started mid-film has a
			     clock that runs from zero, so the served cues are rebased to where
			     this stream began — snapped to the keyframe a remux really starts
			     on. The offset is part of the KEY: swapping a track's src leaves
			     the old cues in the element, so a seek must replace the elements
			     themselves -->
			{#each plan.subtitles as s (`${s.id}:${offset}`)}
				<track
					kind="subtitles"
					srclang={s.lang}
					label={s.lang.toUpperCase()}
					src={`/api/play/${card.kind}/${card.id}/subs/${s.id}.vtt${native ? '' : `?t=${Math.floor(offset)}${plan.mode === 'remux' ? '&snap=1' : ''}`}`}
				/>
			{/each}
		</video>
		{/if}

		<!-- over the picture, not inside the element: see Captions -->
		<Captions {video} track={subsTrack} />

		<!-- While a list is open nothing else may hold the remote. Intercepting the
		     arrows is not enough: a D-pad key is handled by the WebView itself and
		     the page is not always asked, which is how a press meant for the next
		     language reached the position bar behind it. Made unreachable instead
		     of argued with. -->
		<!-- The same bar a record is played from, with what a film adds to it: the
		     languages, and the way into what this copy is. A film's is a visit —
		     it comes when it is asked for and leaves a few seconds later — and
		     that is the only thing about it that differs. -->
		<div class="furniture" inert={remote.menu !== null || (!remote.inBar && remote.peek)}>
			{#snippet filmKeys()}
				{#if remote.scrubbing && chapterAt(position)}
					{@const scene = chapterAt(position)}
					<span class="scene">
						{t('play.chapter', { number: String(scene?.number ?? 0) })}{scene?.title
							? ` · ${scene.title}`
							: ''}
					</span>
				{/if}
				{#if audioList().length > 1}
					<Press tone="key" data-control data-menu="audio" onclick={() => remote.openMenu('audio')}>{audioLabel()}</Press>
				{/if}
				{#if subList().length}
					<Press tone="key" data-control data-menu="subs" onclick={() => remote.openMenu('subs')}>{subLabel()}</Press>
				{/if}
				{#if (castable || boxes.length) && !engine.on && !surface.isTv}
					<Press tone="key" data-control data-menu="cast" on={casting} onclick={castTo} title={t('play.cast')} label={t('play.cast')}>
						<Icon name="cast" size={16} />
					</Press>
				{/if}
				{#if !engine.on && !surface.isTv}
					<Press tone="key" data-control onclick={toggleFull} title={t('play.fullscreen')} label={t('play.fullscreen')}>
						<Icon name={full ? 'shrink' : 'expand'} size={16} />
					</Press>
				{/if}
				<Press tone="key" data-control onclick={() => (showInfo = !showInfo)} title={t('play.info')} label={t('play.info')}>
					<Icon name="info" size={16} />
				</Press>
			{/snippet}
			<PlayerBar
				art={art(card.image, 92)}
				title={plan?.title ?? card.title}
				subtitle={[card.subtitle ? String(card.subtitle) : '', seasonLeft].filter(Boolean).join(' · ')}
				{position}
				{total}
				going={!paused}
				{toggle}
				seek={seekTo}
				away={surface.isTv && !remote.inBar && !remote.peek}
				{ends}
				extras={filmKeys}
			/>
		</div>

		{#if offerSkip}
			<div class="onward" inert={remote.menu !== null}>
				<Press tone="go" onclick={skipIntro}>{t('play.skipIntro')}</Press>
			</div>
		{:else if offerNext && plan.next}
			<div class="onward" inert={remote.menu !== null}>
				<Press tone="go" onclick={playNext}>
					{t('play.nextEpisode', { episode: episodeLabel(plan.next.season_number, plan.next) })}
				</Press>
			</div>
		{/if}

		{#if remote.menu}
			<Choose
				over
				options={remote.menu === 'cast'
					? [
							...boxes.map((box) => ({ key: String(box.id), label: box.name })),
							...(castable ? [{ key: 'other', label: t('cast.otherDevice') }] : [])
						]
					: remote.menu === 'audio'
						? audioList().map((a) => ({ key: String(a.index), label: soundName(a) }))
						: [
								{ key: 'off', label: t('play.subtitlesOff') },
								...subList().map((sub) => ({ key: String(sub.index), label: subtitleName(sub) }))
							]}
				chosen={remote.menu === 'cast'
					? casting
						? ['other']
						: []
					: remote.menu === 'audio'
						? [String(nowAudio())]
						: [nowSub() === null ? 'off' : String(nowSub())]}
				onpick={(key) => {
					const menu = remote.menu;
					remote.closeMenu();
					if (menu === 'cast') {
						const box = boxes.find((b) => String(b.id) === key);
						if (box) void sendTo(box);
						else void elsewhere();
					} else if (menu === 'audio') takeAudio(Number(key));
					else takeSub(key === 'off' ? null : Number(key));
				}}
				onclose={() => remote.menu && remote.closeMenu()}
			/>
		{/if}

		{#if showInfo && plan}
			<FilmInfo
				{plan}
				{video}
				onEngine={engine.on}
				rebuilt={engine.rebuilt}
				{efficient}
				engine={{ decoder: engine.decoder, dropped: engine.dropped, picture: engine.picture }}
				screen={screenSize()}
			/>
		{/if}
	{/if}
</div>

<style>
	.stage {
		position: fixed;
		inset: 0;
		z-index: 30;
		background: var(--picture-ground);
		/* its own, rather than inherited from a rule about hiding the page
		   behind it: the picture is centred in a column of its own */
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	/* The picture is drawn on a surface behind this page, so anything opaque here
	   is a black rectangle over a film. */
	.stage.engine {
		background: transparent;
		/* the film's own surface is inside the part being hidden, so it says
		   plainly that it is not one of the things getting out of the way */
		visibility: visible;
	}
	/* Full screen is the picture, centred in its own shape, and nothing else.
	   The bar and the close button fade rather than vanish so that moving the
	   mouse brings back what was there rather than something new. */
	.stage.full .furniture,
	.stage.full .close,
	.stage.full :global(.info) {
		transition: opacity 200ms ease;
	}
	.stage.idle {
		cursor: none;
	}
	/* above the bar, at the edge the eye goes to when the credits start */
	.onward {
		position: absolute;
		right: 2rem;
		bottom: calc(var(--tv-bar-h, 4.5rem) + 1.5rem);
		z-index: 2;
	}
	.stage.idle .furniture,
	.stage.idle .close,
	.stage.idle :global(.info) {
		opacity: 0;
		pointer-events: none;
	}
	video {
		flex: 1;
		width: 100%;
		min-height: 0;
		background: var(--picture-ground);
		object-fit: contain;
	}
	/* On a television the picture is the screen. The bar lies over it rather than
	   taking a strip away from it, which is what made a film play in a box with a
	   black shelf under it. */
	.stage.tv video {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}
	.close {
		position: absolute;
		top: 0.6rem;
		right: 0.8rem;
		z-index: 2;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 50%;
		border: none;
		background: var(--on-picture-faint);
		color: var(--on-picture);
		font-size: var(--fs-2xl);
		line-height: 1;
		cursor: pointer;
		transition: opacity 160ms ease;
	}
	.furniture {
		transition: opacity 160ms ease;
	}
	/* Only while moving through the film, and only where there is a scene to
	   name — a label that is always there is furniture. */
	.scene {
		color: var(--accent);
		font-size: var(--fs-l);
		white-space: nowrap;
		max-width: 22rem;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.problem {
		margin: auto;
		padding: 1.5rem;
		color: var(--danger);
		text-align: center;
		max-width: 34rem;
	}
</style>
