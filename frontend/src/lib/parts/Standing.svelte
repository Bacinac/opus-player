<script lang="ts">
	import { formatNumber, t } from '$lib/i18n';
	import type { Standing } from '$lib/ask/guess';
	import { count } from '$lib/say/count';

	let { standing, mine, best = false }: { standing: Standing[]; mine: string; best?: boolean } = $props();
</script>

<ol class="table">
	{#each standing as row (row.key)}
		<li class:me={row.key === mine}>
			<span class="name">{row.name}</span>
			<span class="fact">{count(row.rounds, 'rounds').text}</span>
			{#if best}<span class="fact">{t('guess.best', { n: formatNumber(row.best) })}</span>{/if}
			<span class="points">{formatNumber(row.points)}</span>
		</li>
	{/each}
</ol>

<style>
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
	.fact {
		color: var(--muted);
		font-size: 0.85em;
	}
	.points {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
</style>
