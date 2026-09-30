<script lang="ts">
	// One season's episodes, wherever they are being read: in the panel a card
	// opens, or on the series' own page. The row and the tags are the package's,
	// so a line here reads exactly as the same line reads in the Library — what
	// differs is only what this module knows: what the file weighs, and that
	// pressing it plays it.

	import { Tag } from '$lib/kit';
	import { EpisodeRow, StateMark } from '$lib/opus';
	import { formatDate, t } from '$lib/i18n';
	import { watched } from '$lib/keep/watched.svelte';
	import { aired } from '$lib/say/episode';
	import { episodeName, episodeTags } from '$lib/say/says';
	import type { EpisodeEntry, SeasonView } from '$lib/keep/types';

	let {
		season,
		onplay,
		onask,
		/** what an episode is about, which is worth the two lines on a page and
		    not in a panel over the shelf it was opened from */
		told = false
	}: {
		season: SeasonView;
		onplay?: (season: SeasonView, episode: EpisodeEntry) => void;
		/** what pressing a line that is not here does. Without it such a line is
		 *  not a line at all: the remote cannot land on it and nobody can read
		 *  what the episode is, let alone go and look for it. */
		onask?: (season: SeasonView, episode: EpisodeEntry) => void;
		told?: boolean;
	} = $props();
</script>

<div class="episodes">
	{#each season.episodes as e (e.number)}
		<EpisodeRow
			number={e.number}
			title={episodeName(season.number, e)}
			description={told ? (e.overview ?? '') : ''}
			runtime={e.runtime_min ?? null}
			seen={watched.has('episode', e.id) ? t('series.seen') : ''}
			part={watched.part('episode', e.id)}
			dim={!e.playable}
			onpick={e.playable && onplay
				? () => onplay(season, e)
				: onask
					? () => onask(season, e)
					: undefined}
		>
			{#snippet meta()}
				{#if e.air_date && !aired(e)}<span class="when">{formatDate(e.air_date)}</span>{/if}
				{#each episodeTags(season, e) as said (said.text)}
					{#if said.icon}
						<StateMark icon={said.icon} tone={said.tone} text={said.title ? `${said.text} · ${said.title}` : said.text} />
					{:else}
						<Tag tone={said.tone}>{said.text}</Tag>
					{/if}
				{/each}
			{/snippet}
		</EpisodeRow>
	{/each}
</div>

<style>
	.episodes {
		display: grid;
		gap: 0.25rem;
	}
	.when {
		font-size: var(--fs-s);
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
</style>
