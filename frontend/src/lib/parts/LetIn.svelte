<script lang="ts">
	// What a television shows instead of a login form.
	//
	// A box cannot be asked to sign in. Its whole input is four arrow keys, and a
	// password typed with a remote is a password that ends up short, shared, and
	// eventually the answer to how somebody else's television got in. So it shows
	// a code and waits for somebody who is already signed in to say yes to it,
	// from a screen with a keyboard on it.
	//
	// The code is enormous on purpose. It is being read across a room by somebody
	// holding a phone, and every character it saves them squinting at is a
	// character they do not mistype.
	//
	// Built as a sibling of the profile chooser rather than as a web card. They
	// are the two screens a television shows before it shows anything of the
	// library, and a household that meets one and then the other should not feel
	// it changed applications on the way.

	import { formatNumber, t } from '$lib/i18n';
	import { request } from '$lib/kit';
	import { surface } from '$lib/keep/surface.svelte';
	import { focusFirst } from '$lib/tv/spatial.svelte';
	import Press from '$lib/tvui/Press.svelte';

	let { onin }: { onin: () => void } = $props();

	let code = $state('');
	let minutes = $state(0);
	let problem = $state<'' | 'letIn.unreachable' | 'letIn.tooMany'>('');
	let asked = 0;
	let timer: ReturnType<typeof setInterval> | undefined;

	// Often enough that saying yes feels like it took effect, rarely enough that
	// a television left on this screen overnight is not a request a second.
	const EVERY = 3000;

	start();

	async function start() {
		stop();
		problem = '';
		code = '';
		let refused = false;
		const said = await request<{ id: number; code: string; minutes?: number }>(
			'/api/auth/pair',
			{ method: 'POST' },
			{ on: { 429: () => (refused = true) }, failed: () => {} }
		);
		if (!said?.code) {
			problem = refused ? 'letIn.tooMany' : 'letIn.unreachable';
			// the only thing on this screen a remote can press, so it has to be
			// holding the remote — a button nothing is focused on is a button
			// that does not exist on a television
			if (surface.isTv) setTimeout(() => focusFirst('.letin .press'), 0);
			// and the door is asked again by itself: a box whose backend was
			// restarting is still one of ours once it is back
			timer = setInterval(onin, EVERY * 5);
			return;
		}
		code = said.code;
		minutes = said.minutes ?? 0;
		asked = said.id;
		timer = setInterval(watch, EVERY);
	}

	function stop() {
		if (timer) clearInterval(timer);
		timer = undefined;
	}

	let watched = 0;

	async function watch() {
		// the code ran out while nobody was looking. Asking again is what a
		// person would do, so it is done for them rather than shown as an error
		// they have to clear
		const said = await request<{ in: boolean }>(`/api/auth/pair/${asked}`, {}, {
			on: { 404: () => start() },
			failed: () => {}
		});
		if (said?.in) {
			stop();
			onin();
			return;
		}
		// the box may have been let back in some other way — its old credential
		// answering again once the backend is up — so the door is asked as well
		watched += 1;
		if (watched % 10 === 0) onin();
	}

	$effect(() => stop);
</script>

<div class="letin" class:tv={surface.isTv}>
	{#if problem}
		<h1>{t(problem)}</h1>
		<Press onclick={start}>{t('letIn.again')}</Press>
	{:else if code}
		<h1>{t('letIn.says')}</h1>
		<p class="code">{code}</p>
		<p class="where">{t('letIn.where')}</p>
		{#if minutes}<p class="runs">{t('letIn.runsOut', { minutes: formatNumber(minutes) })}</p>{/if}
	{:else}
		<h1>{t('common.loading')}</h1>
	{/if}
</div>

<style>
	/* the same ground the profile chooser stands on: these two are met one after
	   the other and are one screen as far as anybody watching is concerned */
	.letin {
		/* the whole screen, not most of it. Centring inside 70vh puts a door
		   screen in the upper two thirds, which on a desk is a considered
		   margin and across a room is simply not centred. */
		min-height: 100vh;
		display: grid;
		align-content: center;
		justify-items: center;
		gap: 1rem;
		padding: 2rem 1rem;
		text-align: center;
	}
	h1 {
		margin: 0;
		font-weight: 500;
		font-size: var(--fs-xl);
		color: var(--muted);
	}
	p {
		margin: 0;
		max-width: 34rem;
	}
	/* read across a room, so it is sized for the room and not for the text
	   around it. Tabular figures because a code that reflows as it is read is a
	   code that gets read twice. */
	.code {
		font-size: clamp(3rem, 11vw, 6.5rem);
		font-weight: 600;
		letter-spacing: 0.14em;
		font-variant-numeric: tabular-nums;
		line-height: 1.1;
		color: var(--bright, var(--text));
		white-space: nowrap;
	}
	.where {
		font-size: var(--fs-l);
	}
	.runs {
		color: var(--muted);
		font-size: var(--fs-m);
	}

	/* Ten feet away. The code is already sized off the viewport; what has to
	   grow with it is everything that explains it, or the screen reads as one
	   enormous number floating over text nobody can make out. */
	.tv {
		gap: 1.6rem;
	}
	.tv h1 {
		font-size: var(--fs-2xl);
	}
	.tv .code {
		letter-spacing: 0.16em;
	}
	.tv .where {
		font-size: var(--fs-2xl);
		max-width: 46rem;
		line-height: 1.45;
	}
	.tv .runs {
		font-size: var(--fs-xl);
	}
</style>
