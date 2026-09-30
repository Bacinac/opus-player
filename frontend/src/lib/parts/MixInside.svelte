<script lang="ts">
	import { t } from '$lib/i18n';
	import { Heading, request } from '$lib/kit';
	import Press from '$lib/tvui/Press.svelte';
	import type { Card } from '$lib/keep/types';

	let {
		card,
		onwant
	}: {
		card: Card;
		onwant?: (c: Card, seasons: number[], only: boolean) => void;
	} = $props();

	// A mix a catalogue offered is a name and a picture until you can see whose music
	// is in it, and each of those is somebody the library can be asked for.
	let inside = $state<{ title: string; artist: string; album: string }[] | null>(null);

	$effect(() => {
		const holds = card.kind === 'music' ? card.holds : null;
		inside = null;
		if (!holds) return;
		const stop = new AbortController();
		void request<typeof inside>(`/api/explore/music/${holds}/${card.id}`, {
			signal: stop.signal
		}).then((got) => (inside = got));
		return () => stop.abort();
	});
</script>

{#if inside?.length}
	<div class="band">
		<Heading label={t('sheet.inside')} count={inside.length} />
	</div>
	<ul class="inside">
		{#each inside as track (track.title + track.artist)}
			<li>
				<span class="song">
					<strong>{track.title}</strong>
					<em>{track.artist}</em>
				</span>
				{#if onwant}
					<Press
						tone="pill"
						onclick={() =>
							onwant(
								{
									...card,
									kind: 'music',
									person: false,
									artist: track.artist,
									album: track.album
								},
								[],
								false
							)}
					>
						{t('explore.want')}
					</Press>
				{/if}
			</li>
		{/each}
	</ul>
{/if}

<style>
	.band {
		grid-column: 1 / -1;
	}
	/* whose music is in a mix, and a way to take each of them */
	.inside {
		grid-column: 1 / -1;
		display: grid;
		gap: 0.3rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.inside li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.35rem 0;
		border-bottom: 1px solid color-mix(in srgb, var(--border) 35%, transparent);
	}
	.inside .song {
		min-width: 0;
	}
	.inside strong {
		display: block;
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.inside em {
		font-style: normal;
		color: var(--muted);
		font-size: 0.88em;
	}
</style>
