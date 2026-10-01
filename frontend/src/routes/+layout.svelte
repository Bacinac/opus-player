<script lang="ts">
	import '../app.css';
	import { afterNavigate, goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Toasts, narrow, onUnauthorized, toasts } from '$lib/kit';
	import { pageWord, pagesUnder } from '$lib/say/ways';
	import { Login, Shell, icons, me, version } from '$lib/opus';
	import { t } from '$lib/i18n';
	import { MODULE, MODULES } from '$lib/ask/modules';
	import { captions } from '$lib/keep/captions.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	// `nav` here is already the list of sections, so the store comes in under
	// what it answers: where you are and where the ring was.
	import { nav as where } from '$lib/tvui/nav.svelte';
	import { give } from '$lib/keep/give.svelte';
	import { arrows } from '$lib/tv/spatial.svelte';
	import { goBack, ladder, onBack } from '$lib/keep/back.svelte';
	import { tvFrame } from '$lib/tv/frame.svelte';
	import { opened } from '$lib/keep/opened.svelte';
	import Leave from '$lib/tv/Leave.svelte';
	import { rung } from '$lib/tv/rung.svelte';
	import Ground from '$lib/tv/Ground.svelte';
	import Rail from '$lib/tv/Rail.svelte';
	import { shelf } from '$lib/keep/shelf.svelte';
	import { cast } from '$lib/keep/cast.svelte';
	import NowPlaying from '$lib/parts/NowPlaying.svelte';
	import OnTelevision from '$lib/parts/OnTelevision.svelte';
	import SentPhoto from '$lib/parts/SentPhoto.svelte';
	import Play from '$lib/screens/Play.svelte';
	import { film } from '$lib/keep/film.svelte';
	import { tvFilm } from '$lib/keep/tvFilm.svelte';
	import { shown } from '$lib/keep/tvPhoto.svelte';
	import Profiles from '$lib/parts/Profiles.svelte';
	import LetIn from '$lib/parts/LetIn.svelte';
	import { watching } from '$lib/keep/watching.svelte';
	import { forgetKeys } from '$lib/keep/vault.svelte';
	import { queue } from '$lib/keep/queue.svelte';
	import type { Profile } from '$lib/keep/types';
	import { onMount } from 'svelte';

	let { children } = $props();
	const demo = import.meta.env.VITE_OPUS_DEMO === '1';
	let noticesHeight = $state(0);

	let checked = 0;

	async function check() {
		// where this is running goes with the question, because the answer
		// differs: a television is answered as the box it is, whatever else its
		// browser holds
		const said = await me.check(`?surface=${surface.current}`);
		checked = Date.now();
		// through the door is not the same as being somebody: the profile is
		// picked after it, and stays null until it is
		watching.profile = (said.profile as Profile | undefined) ?? null;
		watching.person = String(said.person ?? '');
		if (!watching.person)
			void forgetKeys().catch((why) => toasts.error(t('vault.forgetFailed', { detail: String(why) })));
		// the arrangement whoever holds this screen chose last time: the profile
		// picked on it, or the box itself when nobody is
		shelf.adopt(
			watching.profile?.key ?? null,
			Boolean(said.box),
			String(said.shelf_orders ?? '{}')
		);
	}

	// a refusal anywhere is a question for the door, asked at most every few
	// seconds: a wall of thumbnails refused together is one question
	onUnauthorized(() => {
		if (Date.now() - checked > 5000) void check();
	});

	onMount(() => {
		surface.init();
		captions.init();
		void check();
		const unarrow = arrows();
		return unarrow;
	});

	// the sound outputs are worth knowing only once somebody is in — asked
	// earlier they would answer 401 and the door screen would wear the error
	let castLoaded = false;
	$effect(() => {
		if (watching.profile && !castLoaded) {
			castLoaded = true;
			void cast.load();
			void opened.ask();
			if (!surface.isTv) void tvFilm.adopt();
		}
	});

	let giver = $state<HTMLInputElement>();

	// Somewhere to go back TO, which is not the same as a step that is
	// registered: every rung that would answer a press says so for itself, and
	// the ones that are only standing by say nothing.
	const canGoBack = $derived(!surface.isTv && ladder.holding());

	const hand = async () => {
		const files = [...(giver?.files ?? [])];
		if (giver) giver.value = '';
		if (files.length) await give.put(files);
	};

	afterNavigate(({ from, to }) => {
		// a navigation begun before the first one has landed comes from no url
		if (from?.url && to?.url) rung.went(from.url, to.url);
	});

	// Where the ladder ends. Nothing was standing over anything, so back means
	// leave what you are in. A remote climbs (`rung`); everywhere else back is
	// where you came from, whatever that was — coming to the records from a film
	// and landing on the home screen is not going back, it is being sent
	// somewhere.
	$effect(() =>
		onBack(
			() => {
				if (surface.isTv) return rung.climb(page.url);
				history.back();
				return true;
			},
			() => (surface.isTv ? rung.holds(page.url) : page.url.pathname !== '/' || rung.asked(page.url))
		)
	);

	// The wrapper asks this, and a keyboard's Escape is the same press.
	$effect(() => {
		window.opusBack = goBack;
		function onkey(event: KeyboardEvent) {
			if (event.key !== 'Escape' && event.key !== 'Backspace') return;
			const on = document.activeElement as HTMLElement | null;
			if (on && (on.tagName === 'INPUT' || on.tagName === 'TEXTAREA')) return;
			if (goBack()) event.preventDefault();
		}
		window.addEventListener('keydown', onkey);
		return () => {
			delete window.opusBack;
			window.removeEventListener('keydown', onkey);
		};
	});

	tvFrame();

	// A newer build waits while this screen is in use for something no element
	// on the page shows: a film or a record on the engine, a photograph a phone
	// is showing. The reload would stop it, and on a television the engine would
	// play on with nothing left on the page that knows it is there.
	// A device this screen only shows plays on, and is shown again after; a
	// television following the radio all evening would otherwise keep its old
	// build all evening, and take films with it.
	const idle = () =>
		film.screens === 0 && !shown.photo && (cast.following || (!queue.playing && !cast.playing));
	version.holdWhile(() => !idle());
	cast.fresh = async () => !(await version.check());

	// The sections live in the frame's own nav, where Downloads and Library keep
	// theirs: plain links it marks as current by comparing the path. A phone gets
	// the same list along the bottom instead, because the top of a phone is the
	// part one hand cannot reach — and that bar has no room for the pages under a
	// section, so on a phone they stay the pills in the page's head.
	// The photographs are the household's own. A guest is trusted with the
	// address and not handed the family album, so the section is absent rather
	// than present and refused — and the address bar is told as well as the
	// list, because a page whose every request the door turns away is worse than
	// a page that was never offered.
	const pagesOf = (section: string) =>
		surface.isTv || narrow.current
			? undefined
			: pagesUnder(section).map((way) => {
					const find = way === 'spell' && section !== 'photos' ? 'search' : way;
					return {
						href: `/${section}?find=${find}`,
						label: t(pageWord(section, way) as never),
						active:
							page.url.pathname === `/${section}` && page.url.searchParams.get('find') === find
					};
				});
	const nav = $derived([
		...(surface.isTv ? [] : [{ href: '/', label: t('nav.home'), icon: icons.home }]),
		{ href: '/movies', label: t('nav.movies'), icon: icons.movies, children: pagesOf('movies') },
		{ href: '/series', label: t('nav.series'), icon: icons.series, children: pagesOf('series') },
		{ href: '/music', label: t('nav.music'), icon: icons.music, children: pagesOf('music') },
		...(surface.isTv ? [{ href: '/radio', label: t('find.radio') }] : []),
		...(me.guest
			? []
			: [
					{
						href: '/photos',
						label: t('nav.photos'),
						icon: icons.photos,
						children: pagesOf('photos')
					}
				])
	]);

	$effect(() => {
		if (me.guest && page.url.pathname.startsWith('/photos')) goto('/');
	});

</script>

{#if me.open === null && me.unreachable}
	<p class="unreachable">{t('common.unreachable')}</p>
	<Toasts />
{:else if me.open === false && surface.isTv}
	<!-- a box is let in, not signed in: it shows a code and waits for somebody
	     who is already signed in to say yes to it. Wrapped like the profile
	     chooser it is met just before, because they are one screen as far as
	     anybody watching is concerned -->
	<div class="surface-{surface.current}">
		<LetIn onin={check} />
	</div>
	<Toasts />
{:else if me.open === false}
	<!-- the door is told which surface is asking, because what it hands back
	     differs — and on a television it hands back nothing at all -->
	<Login module={MODULE} onin={check} also={{ surface: surface.current }} />
	<Toasts />
{:else if me.open && !watching.profile}
	<div class="surface-{surface.current}">
		<Profiles onpicked={check} />
	</div>
	<Toasts />
{:else if me.open}
	<div
		class="surface-{surface.current}"
		class:deep={where.level === 2}
		style:--shell-notices-h="{noticesHeight}px"
	>
		<!-- On a television the sections go down the side, so the frame's own row of
		     words is not there to be walked through on the way to the shelf. -->
		<!-- who is watching is not a place in the rail: it is one of the things
		     back offers when there is nowhere left to go -->
		{#if surface.isTv}
			<!-- the picture first, because it is the ground everything else is on -->
			<Ground />
			<!-- It stands, on every screen. The reason is in Rail's own header:
			     a menu that is not there is a menu you have to remember. It was
			     put behind the home screen as a drive-by in a commit about
			     something else, and six things that reserve room for its column
			     went on reserving it — which is most of why four screens out of
			     five stopped looking like the skin they are measured off. -->
			{#if where.level === 1}<Rail {nav} />{/if}
		{/if}
		<Shell
			module={MODULE}
			nav={surface.isTv ? [] : nav}
			heading={!surface.isTv}
			back={canGoBack ? goBack : undefined}
			backLabel={t('common.back')}
			pathname={page.url.pathname}
			modules={surface.isTv ? [] : MODULES}
			alerts={demo ? [{ key: 'demo', message: t('demo.banner'), tone: 'quiet' as const, href: '/demo-credits.html' }] : []}
			bind:noticesHeight
			owner={me.admin}
			account={surface.isTv || !watching.profile
				? undefined
				: {
						username: watching.profile.name,
						href: '/settings',
						// Giving photographs follows the person rather than the page: the photo
						// shelf is the one place somebody is NOT when the evening's pictures are
						// still on their phone.
						does: [{ label: t('photos.give'), onpick: () => giver?.click() }]
					}}
		>
			<!-- no accept: on Android that is what opens the gallery picker, which
			     hands over a copy with the location stripped out of the EXIF -->
			<input bind:this={giver} type="file" multiple onchange={hand} hidden />
			{@render children()}
			<!-- a film somebody elsewhere in the house put on this television -->
			{#if film.asked}
				{#key `${film.asked.kind}:${film.asked.id}`}
					<Play card={film.asked} onclose={() => film.close()} />
				{/key}
			{/if}
			{#if rung.leaving}<Leave />{/if}
			<NowPlaying />
			{#if surface.isTv}<SentPhoto />{/if}
			<!-- one bar along the bottom at a time: a record put on here is the
			     nearer thing, and the film goes on over there regardless -->
			{#if !queue.current}<OnTelevision />{/if}
		</Shell>
	</div>
{/if}

<style>
	.unreachable {
		min-height: 100vh;
		display: grid;
		place-content: center;
		margin: 0;
		padding: 2rem 1rem;
		text-align: center;
		color: var(--muted);
	}
	/* Ten feet away the whole frame grows, not just the cards: the shell's own
	   header and padding are part of what makes a screen readable from a sofa. */
	/* The second level takes the screen, and the column the menu kept goes with
	   it — RELEASED rather than merely uncovered, in the same rule that stops
	   drawing the menu. Six things reserve room for that column: the shelf's
	   tracks, the record page's inset, the transport's left edge. A commit once
	   stopped drawing the menu and left all six reserving anyway, and four
	   screens out of five spent a week laid out for a width that was not there.
	   One variable, so they cannot disagree with it. */
	.surface-tv.deep {
		--rail-w: 0px;
	}
	.surface-tv :global(.shell) {
		max-width: 1800px;
		/* The sections keep a column of their own and the shelf begins after it.
		   No air at the top — the panel that keeps the top of the screen starts
		   there, and a gap above it is a gap it jumps over the first time you
		   scroll. */
		padding: 0 var(--tenfoot-pad, 3rem) 0
			calc(var(--rail-w, 11rem) + var(--tenfoot-pad, 3rem));
		/* A pill says a fact ABOUT the thing on the screen; it is not the thing.
		   At 1.05rem it read as a headline and the row of them took the top of
		   the screen away from what it was describing. Ten feet away it still
		   has to be legible, which is what keeps it a step above the desk's. */
		--tag-font: var(--fs-s);
	}
	/* The notices stand in the page's column, over the screen that starts below
	   them, rather than centred across the menu's mark. */
	.surface-tv :global(.bare .notices) {
		position: fixed;
		top: var(--shell-main-top, 1.5rem);
		left: calc(var(--rail-w, 11rem) + var(--tenfoot-pad, 3rem));
		right: var(--tenfoot-pad, 3rem);
		z-index: 6;
	}
	.surface-tv :global(.bare .alert) {
		margin: 0;
	}
	/* three rem of air under the last row is a measure for a desk, where the
	   window ends where the page ends. A television's does not, and that air was
	   the whole of what a screen scrolled to reach. */
	.surface-tv :global(main) {
		padding-bottom: 0.5rem;
	}
	.surface-mobile :global(.shell) {
		padding: 0 0.9rem;
	}
	/* room for the bar the thumb reaches for */
	.surface-mobile :global(main) {
		padding-bottom: 4.5rem;
	}
</style>
