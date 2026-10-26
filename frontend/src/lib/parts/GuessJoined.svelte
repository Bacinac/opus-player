<script lang="ts">
	// A phone at somebody else's party.
	//
	// It sits down, then follows the screen: asks once a second what is up,
	// shows the question as the screen shows it (smaller, and closer to hand)
	// and sends the one press. Nothing is marked here until the screen has
	// revealed — a phone told early is a phone that can be looked at.

	import { onDestroy } from 'svelte';
	import { formatNumber, t } from '#lib/i18n/index.js';
	import * as guess from '#lib/ask/guess.js';
	import Press from '#lib/tvui/Press.svelte';
	import Who from '#lib/tvui/Who.svelte';
	import GuessStage, { warm } from '#lib/parts/GuessStage.svelte';

	let { partyId, onleave }: { partyId: number; onleave: () => void } = $props();

	const POLL_MS = 1000;

	let party = $state<guess.Party | null>(null);
	// what was pressed for the question now up, kept here so the press shows
	// before the next state arrives
	let chosen = $state<string | null>(null);
	let seen = -1;
	let until = $state(0);
	let gone = $state(false);
	let poll: ReturnType<typeof setInterval> | null = null;

	const me = $derived(party?.players.find((p) => p.key === party?.me) ?? null);
	const question = $derived(party?.question ?? null);
	const standing = $derived([...(party?.players ?? [])].sort((a, b) => b.total - a.total));
	const marks = $derived.by(() => {
		const out: Record<string, guess.Someone[]> = {};
		for (const one of party?.players ?? []) if (one.picked) (out[one.picked] ??= []).push(one);
		return out;
	});

	function take(now: guess.Party) {
		if (now.n !== seen) {
			seen = now.n ?? -1;
			chosen = null;
			if (now.question) warm([now.question]);
		}
		// the clock as the server has it, every time: a phone that counted on
		// its own would drift from the screen it is answering
		if (now.left !== null) until = Date.now() + now.left * 1000;
		party = now;
	}

	$effect(() => {
		void (async () => {
			const joined = await guess.party.join(partyId);
			if (!joined) {
				gone = true;
				return;
			}
			take(joined);
			poll = setInterval(refresh, POLL_MS);
		})();
	});

	onDestroy(() => {
		if (poll) clearInterval(poll);
	});

	async function refresh() {
		if (!party) return;
		const now = await guess.party.state(party.id);
		if (!now) {
			// the screen has left, and the party with it
			gone = true;
			if (poll) clearInterval(poll);
			return;
		}
		take(now);
		if (now.done) await follow(now);
	}

	/** The screen has started again: the same host, a newer party. Sit down at
	 *  it without being asked, since that is what "again" means in a room. */
	async function follow(over: guess.Party) {
		const around = await guess.party.around();
		const next = around.find(
			(p) => p.id > over.id && p.host?.key === over.host?.key && p.mine !== 'host'
		);
		if (!next) return;
		const joined = await guess.party.join(next.id);
		if (joined) {
			seen = -1;
			take(joined);
		}
	}

	async function pick(key: string) {
		if (!party || party.n === null || party.revealed || chosen || me?.answered) return;
		chosen = key;
		await guess.party.answer(party.id, party.n, key);
	}
</script>

{#if gone}
	<div class="wait">
		<p class="says">{t('guess.partyOver')}</p>
		<Press tone="plain" onclick={onleave}>{t('common.back')}</Press>
	</div>
{:else if !party}
	<div class="wait"></div>
{:else if party.done}
	<div class="wait">
		<h3>{t('guess.standing')}</h3>
		<ol class="table">
			{#each standing as one (one.key)}
				<li class:me={one.key === party.me}>
					<span class="name">{one.name}</span>
					<span class="points">{formatNumber(one.total)}</span>
				</li>
			{/each}
		</ol>
		<Press tone="plain" onclick={onleave}>{t('guess.enough')}</Press>
	</div>
{:else if party.n === null || !question}
	<div class="wait">
		<p class="says">{t('guess.waitingHost', { host: party.host?.name ?? '' })}</p>
		<div class="people">
			{#each party.players as one (one.key)}
				<Who name={one.name} colour={one.colour} />
			{/each}
		</div>
		<Press tone="plain" onclick={onleave}>{t('guess.enough')}</Press>
	</div>
{:else}
	<GuessStage
		{question}
		at={party.n}
		count={party.count}
		score={me?.total ?? null}
		{until}
		seconds={party.seconds}
		revealed={party.revealed}
		chosen={chosen ?? me?.picked ?? null}
		correct={party.correct ?? null}
		facts={party.facts ?? null}
		secondFacts={party.second_facts ?? null}
		{marks}
		onpick={chosen || me?.answered ? undefined : pick}
	>
		{#snippet said()}
			<span class="verdict" class:hit={me?.right}>
				{me?.right
					? t('guess.gained', { n: formatNumber(me.points ?? 0) })
					: me?.picked
						? t('guess.wrong')
						: t('guess.timeUp')}
			</span>
		{/snippet}
		{#snippet waiting()}
			{#if chosen || me?.answered}<span class="says">{t('guess.answered')}</span>{/if}
		{/snippet}
	</GuessStage>
{/if}

<style>
	.wait {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 44rem;
		padding: 1rem 0 2rem;
		align-items: flex-start;
	}
	.says {
		color: var(--muted);
		margin: 0;
		line-height: 1.5;
	}
	.people {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.verdict {
		font-weight: 600;
		color: var(--danger);
	}
	.verdict.hit {
		color: var(--ok);
	}
	.table {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		align-self: stretch;
	}
	.table li {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
		padding: 0.4rem 0.7rem;
		border-radius: var(--radius-s, 8px);
		background: var(--card-ground, color-mix(in srgb, var(--bg) 62%, transparent));
	}
	.table li.me {
		border-left: 3px solid var(--accent);
	}
	.name {
		flex: 1;
	}
	.points {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
</style>
