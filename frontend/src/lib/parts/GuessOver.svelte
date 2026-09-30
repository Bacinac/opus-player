<script lang="ts">
	import { formatNumber, t } from '$lib/i18n';
	import type { Standing as Row } from '$lib/ask/guess';
	import Press from '$lib/tvui/Press.svelte';
	import Standing from '$lib/parts/Standing.svelte';

	let {
		rights,
		asked,
		total,
		busy,
		standing,
		mine,
		onbegin,
		onleave
	}: {
		rights: number;
		asked: number;
		total: number;
		busy: boolean;
		standing: Row[];
		mine: string;
		onbegin: () => void;
		onleave: () => void;
	} = $props();
</script>

<div class="over">
	<p class="tally">
		{t('guess.summary', { right: formatNumber(rights), total: formatNumber(asked) })}
	</p>
	<p class="sum">{formatNumber(total)}</p>
	<div class="begin">
		<Press tone="go" disabled={busy} onclick={onbegin}>{t('guess.again')}</Press>
		<Press tone="plain" onclick={onleave}>{t('guess.enough')}</Press>
	</div>
	{#if standing.length}
		<Standing {standing} {mine} />
	{/if}
</div>

<style>
	.over {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 44rem;
		padding: 1rem 0 2rem;
	}
	.begin {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}
	.tally {
		margin: 0;
		color: var(--muted);
	}
	.sum {
		margin: 0;
		font-size: 3rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	@media (max-width: 560px) {
		.begin :global(button) {
			flex: 1;
		}
	}
</style>
