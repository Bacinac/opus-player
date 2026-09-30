<script lang="ts">
	import { formatNumber, t } from '$lib/i18n';
	import Choose, { type Option } from '$lib/tvui/Choose.svelte';
	import Episodes from '$lib/parts/Episodes.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import { haveOf, seasonName } from '$lib/say/says';
	import type { EpisodeEntry, SeasonView } from '$lib/keep/types';

	let {
		seasons,
		chosen = $bindable(),
		owned,
		wanted,
		onget,
		onplay
	}: {
		seasons: SeasonView[];
		chosen: string[];
		owned: boolean;
		wanted: number;
		onget?: (season: number) => void;
		onplay: (season: SeasonView, episode: EpisodeEntry) => void;
	} = $props();

	let picks = $derived<Option[]>(
		seasons.map((s) => ({
			key: String(s.number),
			label: seasonName(s.number),
			note: owned ? haveOf(s.have, s.total) : formatNumber(s.total)
		}))
	);
	let open = $derived(seasons.filter((s) => chosen.includes(String(s.number))));
</script>

<div class="seasons">
	<Choose as="row" options={picks} bind:chosen many all={t('sheet.allSeasons')} />
	{#if wanted}<p class="muted">{t('sheet.chosen', { n: formatNumber(wanted) })}</p>{/if}
</div>
{#each open as s (s.number)}
	<div class="season-head">
		<h3>{seasonName(s.number)} <span class="tag">{haveOf(s.have, s.total)}</span></h3>
		{#if onget && owned && s.total > s.have}
			<Press tone="pill" onclick={() => onget(s.number)}>
				{t('sheet.getSeason', { n: formatNumber(s.total - s.have) })}
			</Press>
		{/if}
	</div>
	<Episodes season={s} {onplay} />
{/each}

<style>
	.seasons {
		display: grid;
		gap: 0.5rem;
		margin: 1.1rem 0 0.7rem;
	}
	.tag {
		font-size: 0.85em;
		color: var(--muted);
	}
	.season-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.8rem;
		margin-top: 1rem;
	}
	.season-head h3 {
		margin: 0;
	}
</style>
