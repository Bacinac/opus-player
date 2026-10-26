<script lang="ts">
	// The screen that asks the room.
	//
	// It opens the party, waits for phones to sit down, and then runs the round
	// the way one person's screen does — puts a question up, watches the clock,
	// reveals, lingers, moves on — except that nothing here is pressed to
	// answer. The answers arrive at the backend from the phones; this screen
	// learns of them by asking, once a second, and reveals early once everybody
	// has answered.

	import { onDestroy } from 'svelte';
	import { formatNumber, t } from '#lib/i18n/index.js';
	import * as guess from '#lib/ask/guess.js';
	import * as sound from '#lib/ask/tick.js';
	import { surface } from '#lib/keep/surface.svelte.js';
	import { focusFirst } from '#lib/tv/spatial.svelte.js';
	import { count } from '#lib/say/count.js';
	import Press from '#lib/tvui/Press.svelte';
	import Who from '#lib/tvui/Who.svelte';
	import GuessStage, { warm } from '#lib/parts/GuessStage.svelte';

	let {
		how,
		resume = null,
		onleave
	}: {
		how: guess.Hardness;
		/** this screen's own party, picked back up rather than opened anew */
		resume?: number | null;
		onleave: () => void;
	} = $props();

	// a room reads slower than one person: the reveal stands a little longer
	const LINGER_MS = 7000;
	const POLL_MS = 1000;
	const AUDIBLE_S = 10;
	const URGENT_S = 5;

	let party = $state<guess.Party | null>(null);
	let phase = $state<'lobby' | 'asking' | 'revealed' | 'done'>('lobby');
	let until = $state(0);
	let ticked = 0;
	let beat: ReturnType<typeof setInterval> | null = null;
	let linger: ReturnType<typeof setTimeout> | null = null;
	let poll: ReturnType<typeof setInterval> | null = null;
	let busy = $state(false);

	const question = $derived(party?.question ?? null);
	const players = $derived(party?.players ?? []);
	const answered = $derived(players.filter((p) => p.answered).length);
	const standing = $derived([...players].sort((a, b) => b.total - a.total));
	const marks = $derived.by(() => {
		const out: Record<string, guess.Someone[]> = {};
		for (const one of players) if (one.picked) (out[one.picked] ??= []).push(one);
		return out;
	});

	function stopBeat() {
		if (beat) clearInterval(beat);
		beat = null;
	}
	function stopLinger() {
		if (linger) clearTimeout(linger);
		linger = null;
	}

	/** Keep the host's copy of the questions: the backend hands them over with
	 *  the party, and every later state carries them again — but a state that
	 *  arrived without them must not take them away. */
	function take(said: guess.Party) {
		party = { ...said, questions: said.questions ?? party?.questions };
	}

	$effect(() => {
		void (async () => {
			const opened =
				resume !== null ? await guess.party.state(resume) : await guess.party.open(how);
			if (!opened || opened.mine !== 'host') {
				onleave();
				return;
			}
			take(opened);
			warm(opened.questions ?? []);
			if (opened.done) {
				phase = 'done';
			} else if (opened.n !== null && !opened.revealed) {
				// picked back up mid-question: the clock is wherever the server says
				phase = 'asking';
				until = Date.now() + (opened.left ?? 0) * 1000;
				ticked = Math.ceil(opened.left ?? 0);
				beat = setInterval(watch, 200);
			} else if (opened.n !== null) {
				phase = 'revealed';
				linger = setTimeout(onward, LINGER_MS);
			}
			poll = setInterval(refresh, POLL_MS);
			if (surface.isTv) setTimeout(() => focusFirst('.lobby button, .over button'), 60);
		})();
	});

	onDestroy(() => {
		stopBeat();
		stopLinger();
		if (poll) clearInterval(poll);
		// a party walked away from is no party: the phones find out by asking,
		// and the rounds at it were never scores
		if (party && !party.done) void guess.party.close(party.id);
	});

	async function refresh() {
		if (!party || busy) return;
		const now = await guess.party.state(party.id);
		if (!now) return;
		take(now);
		// everybody has answered: nobody is waiting on a clock that is only
		// running down for the empty seats
		if (phase === 'asking' && now.players.length && now.players.every((p) => p.answered)) {
			void reveal();
		}
	}

	async function go() {
		if (!players.length) return;
		await ask(0);
	}

	async function ask(n: number) {
		if (!party) return;
		busy = true;
		const said = await guess.party.ask(party.id, n);
		busy = false;
		if (!said) {
			onleave();
			return;
		}
		take(said);
		phase = 'asking';
		until = Date.now() + said.seconds * 1000;
		ticked = Math.ceil(said.seconds);
		stopBeat();
		beat = setInterval(watch, 200);
	}

	function watch() {
		if (phase !== 'asking') return;
		const left = (until - Date.now()) / 1000;
		const second = Math.ceil(left);
		if (second < ticked) {
			ticked = second;
			if (second > 0 && second <= AUDIBLE_S) sound.tick(second <= URGENT_S);
		}
		if (left <= 0) void reveal();
	}

	async function reveal() {
		if (phase !== 'asking' || !party) return;
		stopBeat();
		phase = 'revealed';
		busy = true;
		const said = await guess.party.reveal(party.id);
		busy = false;
		if (said) {
			take(said);
			if (said.players.some((p) => p.right)) sound.right();
			else sound.wrong();
		}
		stopLinger();
		linger = setTimeout(onward, LINGER_MS);
		if (surface.isTv) setTimeout(() => focusFirst('.said button'), 60);
	}

	async function onward() {
		stopLinger();
		if (!party) return;
		const next = (party.n ?? -1) + 1;
		if (next < party.count) {
			await ask(next);
			return;
		}
		phase = 'done';
		sound.over();
		if (surface.isTv) setTimeout(() => focusFirst('.over button'), 60);
	}

	/** The same room again. A new party, and the phones follow it on their
	 *  own: a phone still on the finished one looks for this screen's next. */
	async function again() {
		if (busy) return;
		busy = true;
		const opened = await guess.party.open(how);
		busy = false;
		if (!opened) return;
		take(opened);
		warm(opened.questions ?? []);
		phase = 'lobby';
		if (surface.isTv) setTimeout(() => focusFirst('.lobby button'), 60);
	}
</script>

{#if phase === 'lobby'}
	<div class="lobby">
		<p class="what">{t('guess.lobby')}</p>
		<div class="people">
			{#each players as one (one.key)}
				<Who name={one.name} colour={one.colour} />
			{:else}
				<span class="says">{t('guess.nobody')}</span>
			{/each}
		</div>
		<div class="begin">
			<Press tone="go" disabled={!players.length || busy} onclick={go}>{t('guess.go')}</Press>
			<Press tone="plain" onclick={onleave}>{t('guess.enough')}</Press>
		</div>
	</div>
{:else if phase === 'done'}
	<div class="over">
		<h3>{t('guess.standing')}</h3>
		<ol class="table">
			{#each standing as one (one.key)}
				<li>
					<span class="name"><Who name={one.name} colour={one.colour} /></span>
					<span class="points">{formatNumber(one.total)}</span>
				</li>
			{/each}
		</ol>
		<div class="begin">
			<Press tone="go" disabled={busy} onclick={again}>{t('guess.again')}</Press>
			<Press tone="plain" onclick={onleave}>{t('guess.enough')}</Press>
		</div>
	</div>
{:else if question && party}
	<GuessStage
		{question}
		at={party.n ?? 0}
		count={party.count}
		{until}
		seconds={party.seconds}
		revealed={phase === 'revealed'}
		correct={party.correct ?? null}
		facts={party.facts ?? null}
		secondFacts={party.second_facts ?? null}
		{marks}
		onnext={onward}
	>
		{#snippet said()}
			{#each players as one (one.key)}
				<Who name={one.name} colour={one.colour} tone={one.right ? 'hit' : one.right === false ? 'miss' : null}>
					{one.right ? `+${formatNumber(one.points ?? 0)}` : '✗'}
				</Who>
			{/each}
		{/snippet}
		{#snippet waiting()}
			<span class="says">{count(answered, 'players').text} · {formatNumber(players.length)}</span>
		{/snippet}
	</GuessStage>
{/if}

<style>
	.lobby,
	.over {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 44rem;
		padding: 1rem 0 2rem;
	}
	.what,
	.says {
		color: var(--muted);
		margin: 0;
		line-height: 1.5;
	}
	.people {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		min-height: 2.2rem;
		align-items: center;
	}
	.begin {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}
	.table {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.table li {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.4rem 0.7rem;
		border-radius: var(--radius-s, 8px);
		background: var(--card-ground, color-mix(in srgb, var(--bg) 62%, transparent));
	}
	.table .name {
		flex: 1;
	}
	.points {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
	:global(html.tv) .lobby,
	:global(html.tv) .over {
		max-width: 60rem;
		font-size: var(--fs-xl);
	}
</style>
