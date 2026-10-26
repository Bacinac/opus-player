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
	// Played together, this screen either asks the room (GuessParty) or is one
	// of the phones answering it (GuessJoined); alone, it does both halves.

	import { onDestroy } from 'svelte';
	import { formatNumber, t } from '#lib/i18n/index.js';
	import { keep, recall } from '#lib/kit/index.js';
	import * as guess from '#lib/ask/guess.js';
	import * as sound from '#lib/ask/tick.js';
	import { surface } from '#lib/keep/surface.svelte.js';
	import { played } from '#lib/keep/played.svelte.js';
	import { focusFirst } from '#lib/tv/spatial.svelte.js';
	import { onBack } from '#lib/keep/back.svelte.js';
	import { nav } from '#lib/tvui/nav.svelte.js';
	import GuessIntro from '#lib/parts/GuessIntro.svelte';
	import GuessOver from '#lib/parts/GuessOver.svelte';
	import GuessStage, { warm } from '#lib/parts/GuessStage.svelte';
	import GuessParty from '#lib/parts/GuessParty.svelte';
	import GuessJoined from '#lib/parts/GuessJoined.svelte';

	// how long the reveal stands before the next question comes up on its own.
	// Long enough to look at the photograph, short enough that nobody has to
	// press anything to keep playing.
	const LINGER_MS = 6000;
	// the last stretch of the clock, where a second is heard as well as seen
	const AUDIBLE_S = 10;
	const URGENT_S = 5;
	// how often the intro looks for a party to join
	const LOOK_MS = 3000;

	let stage = $state<'ready' | 'asking' | 'revealed' | 'done' | 'hosting' | 'joined'>('ready');
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
	let parties = $state<guess.OpenParty[]>([]);
	// the party this screen hosts again after a reload, or has joined
	let partyId = $state<number | null>(null);

	const question = $derived(playing?.questions[at] ?? null);
	const total = $derived(told.reduce((sum, one) => sum + one.points, 0));
	const rights = $derived(told.filter((one) => one.right).length);

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

	/* A party somebody opened on another screen, looked for while this one is
	   on the intro: that is where "join" is pressed, so that is where it has to
	   be known about. */
	$effect(() => {
		if (stage !== 'ready') return;
		const look = async () => {
			parties = await guess.party.around();
		};
		void look();
		const every = setInterval(look, LOOK_MS);
		return () => clearInterval(every);
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
		warm(round.questions);
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
		if (surface.isTv) setTimeout(() => focusFirst('.answers button, .pair button'), 60);
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

	function together(resume: number | null = null) {
		sound.muted(quiet);
		partyId = resume;
		stage = 'hosting';
	}

	function join(id: number) {
		partyId = id;
		stage = 'joined';
	}

	function leave() {
		stopBeat();
		stopLinger();
		stage = 'ready';
		playing = null;
		marked = null;
		chosen = null;
		partyId = null;
	}

	function hush() {
		quiet = !quiet;
		sound.muted(quiet);
	}
</script>

{#if stage === 'ready'}
	<GuessIntro
		{how}
		{quiet}
		{busy}
		{standing}
		{mine}
		{parties}
		onharden={harden}
		onhush={hush}
		onbegin={begin}
		ontogether={() => together()}
		onresume={(id) => together(id)}
		onjoin={join}
	/>
{:else if stage === 'hosting'}
	<GuessParty {how} resume={partyId} onleave={leave} />
{:else if stage === 'joined' && partyId !== null}
	<GuessJoined {partyId} onleave={leave} />
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
	<GuessStage
		{question}
		{at}
		count={playing?.questions.length ?? 0}
		score={total}
		{until}
		seconds={playing?.seconds ?? 20}
		revealed={stage === 'revealed'}
		{chosen}
		correct={marked?.correct ?? null}
		facts={marked?.facts ?? null}
		secondFacts={marked?.second_facts ?? null}
		onpick={(key) => answer(key)}
		onnext={onward}
	>
		{#snippet said()}
			<span class="verdict" class:hit={marked?.right}>
				{marked?.right
					? t('guess.gained', { n: formatNumber(marked.points) })
					: chosen
						? t('guess.wrong')
						: t('guess.timeUp')}
			</span>
		{/snippet}
	</GuessStage>
{/if}

<style>
	.verdict {
		font-weight: 600;
		color: var(--danger);
	}
	.verdict.hit {
		color: var(--ok);
	}
</style>
