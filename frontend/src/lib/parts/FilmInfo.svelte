<script lang="ts">
	import { art } from '$lib/ask/art';
	import { t, formatNumber } from '$lib/i18n';
	import { request } from '$lib/kit';
	import { genreName } from '$lib/say/genre';
	import type { Plan } from '$lib/keep/types';
	import Portrait from '$lib/tvui/Portrait.svelte';

	let {
		plan,
		video,
		onEngine,
		rebuilt,
		efficient,
		engine,
		screen
	}: {
		plan: Plan;
		video: HTMLVideoElement | null;
		onEngine: boolean;
		rebuilt: boolean;
		efficient: boolean | null;
		engine: { decoder: string; dropped: number; picture: string };
		screen: string;
	} = $props();

	let quality = $state<{ dropped: number; total: number } | null>(null);
	let buffered = $state(0);
	let server = $state<{ transcodes: { cpu_s: number | null; rss_mb: number | null }[];
		limit: number; gpu: string | null; load?: number[]; cores?: number } | null>(null);

	function sample() {
		if (!video) return;
		const q = video.getVideoPlaybackQuality?.();
		if (q) quality = { dropped: q.droppedVideoFrames, total: q.totalVideoFrames };
		const end = video.buffered.length ? video.buffered.end(video.buffered.length - 1) : 0;
		buffered = Math.max(0, end - video.currentTime);
	}

	async function askServer() {
		// the panel says a dash where the box did not answer
		server = await request<typeof server>('/api/play/stats', {}, { failed: () => {} });
	}

	$effect(() => {
		askServer();
		const beat = setInterval(() => {
			sample();
			askServer();
		}, 2000);
		return () => clearInterval(beat);
	});
</script>

<aside class="info">
	{#if plan.details?.overview || plan.details?.cast?.length}
		<div class="story">
			<h2>{plan.title}</h2>
			<p class="facts">
				{[
					plan.year,
					plan.runtime_min ? t('play.minutes', { n: formatNumber(plan.runtime_min) }) : null,
					...(plan.details.genres ?? []).map(genreName)
				]
					.filter(Boolean)
					.join(' · ')}
			</p>
			{#if plan.details.directors?.length}
				<p class="by">
					<span
						>{plan.details.directors.length > 1
							? t('play.directors')
							: t('play.director')}</span
					>
					{plan.details.directors.join(', ')}
				</p>
			{/if}
			{#if plan.details.overview}
				<p class="overview">{plan.details.overview}</p>
			{/if}
			{#if plan.details.cast?.length}
				<ul class="cast">
					{#each plan.details.cast as person (person.id)}
						<li>
							<Portrait
								rung="beside"
								src={person.profile_url ? art(person.profile_url, 154) : undefined}
								name={person.name}
							/>
							<strong>{person.name}</strong>
							{#if person.character}<em>{person.character}</em>{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	{/if}
	<div>
		<h3>{t('play.server')}</h3>
		<dl>
			<dt>{t('play.source')}</dt>
			<dd>{plan.source.video_codec} · {plan.source.height}p · {plan.source.container}</dd>
			<dt>{t('play.sent')}</dt>
			<dd>
				{onEngine && !rebuilt ? t('play.untouched') : plan.mode}{plan.mode === 'transcode'
					? ` · h264 · ${plan.height}p`
					: ''}
			</dd>
			<dt>{t('play.target')}</dt>
			<dd>
				{onEngine && !rebuilt
					? t('play.noResize')
					: plan.width && plan.height
						? `${plan.width} × ${plan.height}`
						: '—'}
			</dd>
			<dt>{t('play.transcodes')}</dt>
			<dd>
				{server ? `${formatNumber(server.transcodes.length)} / ${formatNumber(server.limit)}` : '—'}{server?.transcodes[0]?.cpu_s != null
					? ` · ${formatNumber(server.transcodes[0].cpu_s)} s cpu · ${formatNumber(server.transcodes[0].rss_mb ?? 0)} MB`
					: ''}
			</dd>
			<dt>{t('play.load')}</dt>
			<dd>
				{server?.load
					? `${server.load.map((n) => formatNumber(n)).join(' · ')} / ${formatNumber(server.cores ?? 0)}`
					: '—'}
			</dd>
		</dl>
	</div>
	<div>
		<h3>{t('play.local')}</h3>
		<dl>
			<dt>{t('play.decoding')}</dt>
			<dd>
				{#if onEngine}
					{engine.decoder || '—'}
				{:else if plan.mode === 'transcode'}
					h264 · {t('play.hardware')}
				{:else if efficient}
					{plan.source.video_codec} · {t('play.hardware')}
				{:else}
					{plan.source.video_codec} · {t('play.software')}
				{/if}
			</dd>
			<dt>{t('play.dropped')}</dt>
			<dd>
				{onEngine
					? formatNumber(engine.dropped)
					: quality
						? `${formatNumber(quality.dropped)} / ${formatNumber(quality.total)}`
						: '—'}
			</dd>
			{#if onEngine}
				<dt>{t('play.picture')}</dt>
				<dd>{engine.picture || '—'}</dd>
			{/if}
			<dt>{t('play.screen')}</dt>
			<dd>{screen}</dd>
			{#if !onEngine}
				<dt>{t('play.buffered')}</dt>
				<dd>{buffered ? `${formatNumber(buffered, { maximumFractionDigits: 0 })} s` : '—'}</dd>
			{/if}
		</dl>
	</div>
</aside>

<style>
	.info {
		max-height: 40vh;
		overflow-y: auto;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr));
		gap: 1.5rem;
		padding: 0.9rem 1.1rem 1.2rem;
		background: var(--bg);
		color: color-mix(in srgb, var(--text) 85%, var(--bg));
		font-size: var(--fs-s);
		border-top: 1px solid var(--border);
	}
	.story {
		grid-column: 1 / -1;
	}
	.story h2 {
		margin: 0;
		font-size: var(--fs-2xl);
		font-weight: 600;
		color: var(--bright, var(--text));
	}
	.story .facts {
		margin: 0.25rem 0 0;
		color: var(--muted);
	}
	.story .by {
		margin: 0.5rem 0 0;
	}
	.story .by span {
		color: var(--muted);
		margin-right: 0.5rem;
	}
	.story .overview {
		margin: 0.6rem 0 0;
		max-width: 62ch;
		font-size: var(--fs-l);
		line-height: 1.5;
		color: var(--text);
	}
	.cast {
		display: flex;
		gap: 1rem;
		margin: 1rem 0 0;
		padding: 0 0 0.3rem;
		list-style: none;
		overflow-x: auto;
		scrollbar-width: none;
	}
	.cast li {
		flex: 0 0 5.5rem;
		text-align: center;
	}
	.cast li :global(.portrait) {
		margin: 0 auto;
	}
	.cast strong {
		display: block;
		margin-top: 0.4rem;
		font-weight: 500;
		color: var(--text);
	}
	.cast em {
		display: block;
		font-style: normal;
		color: var(--muted);
	}
	.info h3 {
		margin: 0 0 0.5rem;
		font-size: var(--fs-xs);
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.info dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.3rem 0.9rem;
		margin: 0;
	}
	.info dt {
		color: var(--muted);
	}
	.info dd {
		margin: 0;
		font-variant-numeric: tabular-nums;
	}
</style>
