<script lang="ts">
	// Tko, gdje, kada — the archive asked back.
	//
	// A photograph on the screen, four answers under it and twenty seconds. What
	// is asked is drawn from what the library actually knows about that picture,
	// so the game can never ask a question the house cannot answer.
	//
	// The clock is the server's. This draws it and makes it audible; the number
	// that is scored is the time between the question being handed out and the
	// answer arriving over there — a screen that timed itself would be timing
	// the thing it is being marked on.
	//
	// Every picture of the round is fetched before the first question is asked.
	// A game with a clock on it cannot also have a spinner.

	import { onDestroy } from 'svelte';
	import { formatNumber, t } from '$lib/i18n';
	import { keep, recall } from '$lib/kit';
	import { cropOf, previewOf } from '$lib/opus';
	import * as guess from '$lib/ask/guess';
	import * as sound from '$lib/ask/tick';
	import { askedOf, photoSays } from '$lib/say/says';
	import { surface } from '$lib/keep/surface.svelte';
	import { played } from '$lib/keep/played.svelte';
	import { focusFirst } from '$lib/tv/spatial.svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { nav } from '$lib/tvui/nav.svelte';
	import Answers from '$lib/tvui/Answers.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import Clock from '$lib/parts/Clock.svelte';
	import GuessIntro from '$lib/parts/GuessIntro.svelte';
	import GuessOver from '$lib/parts/GuessOver.svelte';
	import GuessPicture from '$lib/parts/GuessPicture.svelte';

	// how long the reveal stands before the next question comes up on its own.
	// Long enough to look at the photograph, short enough that nobody has to
	// press anything to keep playing.
	const LINGER_MS = 6000;
	// the last stretch of the clock, where a second is heard as well as seen
	const AUDIBLE_S = 10;
	const URGENT_S = 5;

	let stage = $state<'ready' | 'asking' | 'revealed' | 'done'>('ready');
	let playing = $state<guess.Round | null>(null);
	let at = $state(0);
	let chosen = $state<string | null>(null);
	let marked = $state<guess.Marked | null>(null);
	let told = $state<guess.Marked[]>([]);
	let until = $state(0);
	let quiet = $state(false);
	let standing = $state<guess.Standing[]>([]);
	let mine = $state('');
	let busy = $state(false);

	const question = $derived(playing?.questions[at] ?? null);
	const total = $derived(told.reduce((sum, one) => sum + one.points, 0));
	const rights = $derived(told.filter((one) => one.right).length);

	const picture = (photo: { id: string; turn: number }) => previewOf(photo.id, photo.turn);
	const cropped = (face: number) => `${cropOf(face)}?size=big`;

	/* What is on the stage. A question about who somebody is shows the FACE:
	   the photograph around it answers the question by itself for anybody who
	   recognises the room, the day, or who else is standing there. Once it has
	   been answered the whole photograph comes up — which is what the face was
	   cut out of, and the half of it that was being kept back. */
	const showing = $derived.by(() => {
		if (!question) return '';
		if (question.kind === 'who' && question.face && stage === 'asking') {
			return cropped(question.face);
		}
		return picture(question.photo);
	});

	let beat: ReturnType<typeof setInterval> | null = null;
	let linger: ReturnType<typeof setTimeout> | null = null;
	let ticked = 0;

	function stopBeat() {
		if (beat) clearInterval(beat);
		beat = null;
	}

	function stopLinger() {
		if (linger) clearTimeout(linger);
		linger = null;
	}

	onDestroy(() => {
		stopBeat();
		stopLinger();
	});

	/* Nothing else on the screen while a round is running: the game is the
	   screen, the way a film is. */
	$effect(() => (stage === 'ready' || stage === 'done' ? undefined : nav.takes()));

	$effect(() =>
		onBack(
			() => {
				if (stage === 'ready') return false;
				leave();
				return true;
			},
			// and it says so, because the section's own way out is hidden while a
			// round is running: this is the only one left
			() => stage !== 'ready'
		)
	);

	$effect(() => {
		void (async () => {
			const said = await guess.scores();
			standing = said.standing;
			mine = said.me;
		})();
	});

	/** How hard the faces should be, remembered between rounds. Three stops and
	 *  not a bar to drag: this is played from a sofa as well, and a remote
	 *  cannot drag anything. */
	let how = $state<guess.Hardness>('fair');

	$effect(() => {
		const said = recall('opus.guess.how');
		if (said && said in guess.HARDNESS) how = said as guess.Hardness;
	});

	function harden(pick: guess.Hardness) {
		how = pick;
		keep('opus.guess.how', pick);
	}

	$effect(() => {
		played.playing = stage !== 'ready';
	});

	onDestroy(() => {
		played.playing = false;
	});

	async function begin() {
		if (busy) return;
		busy = true;
		// the browser will not make a sound until somebody has pressed
		// something, and this is that press
		sound.muted(quiet);
		const round = await guess.round(10, how);
		busy = false;
		if (!round) return;
		// every picture, now, while the first question is still being asked for
		// — and the face as well where one is asked about, because that is what
		// goes up first and the photograph only follows the answer
		for (const one of round.questions) {
			new Image().src = picture(one.photo);
			if (one.kind === 'who' && one.face) new Image().src = cropped(one.face);
		}
		playing = round;
		told = [];
		at = 0;
		await ask(0);
	}

	async function ask(n: number) {
		chosen = null;
		marked = null;
		at = n;
		stage = 'asking';
		const round = playing;
		if (!round) return;
		const said = await guess.start(round.id, n);
		// a question with no clock behind it is not a question; the refusal has
		// said itself, and the round goes back to where it can be started again
		if (!said) {
			leave();
			return;
		}
		until = Date.now() + said.seconds * 1000;
		ticked = Math.ceil(said.seconds);
		stopBeat();
		beat = setInterval(watch, 200);
		if (surface.isTv) setTimeout(() => focusFirst('.answers button'), 60);
	}

	/** The clock, watched rather than counted down: a television that dropped
	 *  frames or a tab that was away must not end up believing there is more
	 *  time left than the server thinks. */
	function watch() {
		if (stage !== 'asking') return;
		const left = (until - Date.now()) / 1000;
		const second = Math.ceil(left);
		if (second < ticked) {
			ticked = second;
			if (second > 0 && second <= AUDIBLE_S) sound.tick(second <= URGENT_S);
		}
		if (left <= 0) void answer(null);
	}

	async function answer(key: string | null) {
		if (stage !== 'asking' || !playing) return;
		stopBeat();
		chosen = key;
		stage = 'revealed';
		const said = await guess.answer(playing.id, at, key);
		if (!said) {
			// the mark never came back, so there is nothing to reveal. Standing
			// on a dead question with a stopped clock is the one thing worse
			// than a wrong answer.
			stopLinger();
			linger = setTimeout(onward, 1200);
			return;
		}
		marked = said;
		told = [...told, said];
		if (said.right) sound.right();
		else sound.wrong();
		stopLinger();
		linger = setTimeout(onward, LINGER_MS);
		// the ring must land on something that can still be pressed: an answer
		// is no longer one, and a remote left on a spent button is a remote
		// whose arrows do nothing
		if (surface.isTv) setTimeout(() => focusFirst('.said button'), 60);
	}

	async function onward() {
		stopLinger();
		if (!playing) return;
		if (at + 1 < playing.questions.length) {
			await ask(at + 1);
			return;
		}
		stage = 'done';
		sound.over();
		const said = await guess.scores();
		standing = said.standing;
		mine = said.me;
		if (surface.isTv) setTimeout(() => focusFirst('.over button'), 60);
	}

	function leave() {
		stopBeat();
		stopLinger();
		stage = 'ready';
		playing = null;
		marked = null;
		chosen = null;
	}

	function hush() {
		quiet = !quiet;
		sound.muted(quiet);
	}

	/* What is left of the window under whatever head this surface draws above
	   the game — measured, not guessed at with a viewport fraction. The round
	   must not scroll: pressing an answer near the bottom of a page taller than
	   the window scrolls it, and a question that has walked off the top is a
	   question being answered from memory. */
	let floor = $state<HTMLElement>();
	let room = $state(0);
	$effect(() => {
		// re-read when the stage changes as well as when the window does: the
		// section around the game leaves the screen for the length of a round,
		// which moves the top of this by everything that was above it, and a
		// height measured before it left is a height that no longer fits
		void stage;
		const measure = () => {
			if (!floor) return;
			// what the page puts BELOW this counts too. The frame ends its main
			// with three rems of air, which is right under a shelf and is dead
			// weight under a screen already sized to the window: the round would run
			// off the bottom by exactly that much.
			const below = floor.closest('main');
			const air = below ? parseFloat(getComputedStyle(below).paddingBottom) || 0 : 0;
			room = Math.max(300, window.innerHeight - floor.getBoundingClientRect().top - air - 14);
		};
		measure();
		// after the frame the section unmounts in, or this measures the old top
		const soon = requestAnimationFrame(measure);
		window.addEventListener('resize', measure);
		return () => {
			cancelAnimationFrame(soon);
			window.removeEventListener('resize', measure);
		};
	});

	const options = $derived(question?.options ?? []);
</script>

{#if stage === 'ready'}
	<GuessIntro {how} {quiet} {busy} {standing} {mine} onharden={harden} onhush={hush} onbegin={begin} />
{:else if stage === 'done'}
	<GuessOver
		{rights}
		asked={told.length}
		{total}
		{busy}
		{standing}
		{mine}
		onbegin={begin}
		onleave={leave}
	/>
{:else if question}
	<div class="round" bind:this={floor} style:height={room ? `${room}px` : undefined}>
		<header>
			<span class="asked">{askedOf(question.kind)}</span>
			<span class="where">
				{t('guess.of', { n: formatNumber(at + 1), total: formatNumber(playing?.questions.length ?? 0) })}
			</span>
			<span class="score">{formatNumber(total)}</span>
			<Clock {until} seconds={playing?.seconds ?? 20} running={stage === 'asking'} />
		</header>

		<GuessPicture
			src={showing}
			frame={question.frame}
			marked={question.kind === 'who' && stage === 'revealed'}
		/>

		<Answers
			{options}
			{chosen}
			correct={marked?.correct ?? null}
			revealed={stage === 'revealed'}
			onpick={(key) => answer(key)}
		/>

		<!-- always there, empty while the question stands: a row that appears
		     with the answer would move the answers under the hand reaching for
		     them, and the clock is running -->
		<div class="said">
			{#if stage === 'revealed'}
				<span class="verdict" class:hit={marked?.right}>
					{marked?.right
						? t('guess.gained', { n: formatNumber(marked.points) })
						: chosen
							? t('guess.wrong')
							: t('guess.timeUp')}
				</span>
				{#if marked}<span class="truth">{photoSays(marked.facts)}</span>{/if}
				<Press tone="plain" onclick={onward}>{t('guess.next')}</Press>
			{/if}
		</div>
	</div>
{/if}

<style>
	.round {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
		height: 100%;
		min-height: 0;
	}
	header {
		display: flex;
		align-items: center;
		gap: 0.9rem;
	}
	.asked {
		font-size: var(--fs-xl);
		font-weight: 600;
		flex: 1;
	}
	.where,
	.score {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.score {
		color: var(--text);
		font-weight: 600;
	}

	.said {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		flex-wrap: wrap;
		min-height: 2.6rem;
	}
	.verdict {
		font-weight: 600;
		color: var(--danger);
	}
	.verdict.hit {
		color: var(--ok);
	}
	.truth {
		color: var(--muted);
		flex: 1;
	}

	:global(html.tv) .asked {
		font-size: var(--fs-2xl);
	}

	/* A television is wide, and the question was laid out down it: header over
	   picture over four answers over a line of comment, each taking its height
	   from the one above until the photograph — which is the whole question —
	   had what was left, and the column still ran off the bottom.
	
	   Two columns instead. The picture takes the room a sixteen-by-nine screen
	   actually has, and the answers stand beside it in one narrow rail rather
	   than in a block under it.

	   What the photograph turns out to have been is a sentence, and it gets the
	   whole width to be one in: under the picture alone it was set in the same
	   narrow column and broke into three lines while half the screen beside it
	   stood empty. */
	:global(html.tv) .round {
		display: grid;
		grid-template-columns: 1fr 30rem;
		grid-template-rows: auto minmax(0, 1fr) auto;
		grid-template-areas:
			'head head'
			'stage answers'
			'said said';
		column-gap: 2.5rem;
		row-gap: 0.9rem;
	}
	:global(html.tv) .round > header {
		grid-area: head;
	}
	:global(html.tv) .round > :global(.answers) {
		grid-area: answers;
		align-content: center;
	}
	:global(html.tv) .said {
		grid-area: said;
	}
	:global(html.tv) .said {
		font-size: var(--fs-xl);
		min-height: 3.4rem;
	}


</style>
