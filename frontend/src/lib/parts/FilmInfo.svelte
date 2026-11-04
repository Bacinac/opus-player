<script lang="ts">
	import { art } from '#lib/ask/art.js';
	import { t, formatNumber } from '#lib/i18n/index.js';
	import { request } from '#lib/kit/index.js';
	import Clamped from '#lib/opus/Clamped.svelte';
	import { genreName } from '#lib/say/genre.js';
	import { pictureSize as size } from '#lib/say/says.js';
	import type { Plan } from '#lib/keep/types.js';
	import Portrait from '#lib/tvui/Portrait.svelte';

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
		engine: { decoder: string; dropped: number; picture: string; rate: number; stalls: number; bandwidth: number };
		screen: string;
	} = $props();

	let opened = $state(false);

	const mbits = (kbps: number) => t('play.mbits', { n: formatNumber(kbps / 1000, { maximumFractionDigits: 1 }) });
	const exact = (n: number) => formatNumber(n, { maximumFractionDigits: 3 });
	const said = (...parts: (string | null | false | undefined)[]) => parts.filter(Boolean).join(' · ');

	let quality = $state<{ dropped: number; total: number } | null>(null);
	let buffered = $state(0);
	let decoded = $state('');
	let server = $state<{ transcodes: { cpu_s: number | null; rss_mb: number | null }[];
		limit: number; gpu: string | null; load?: number[]; cores?: number } | null>(null);

	const directors = $derived((plan.details?.directors ?? []).map((who) => who.name));
	const facts = $derived(
		said(
			plan.year ? String(plan.year) : null,
			plan.runtime_min ? t('play.minutes', { n: formatNumber(plan.runtime_min) }) : null,
			...(plan.details?.genres ?? []).map(genreName),
			directors.length
				? `${directors.length > 1 ? t('play.directors') : t('play.director')} ${directors.join(', ')}`
				: null
		)
	);

	const now = $derived([
		{
			label: t('play.picture'),
			value: said(
				onEngine ? engine.picture : decoded || (plan.width && plan.height ? size(plan.width, plan.height) : null),
				onEngine && !rebuilt ? plan.source.video_codec : (plan.codec ?? plan.source.video_codec),
				plan.kbps ? mbits(plan.kbps) : null
			)
		},
		{
			label: t('play.source'),
			value: said(
				size(plan.source.width, plan.source.height),
				plan.source.video_codec,
				plan.source.container,
				plan.source.frame_rate ? t('play.fps', { n: exact(plan.source.frame_rate) }) : null
			)
		},
		{ label: t('play.screen'), value: said(screen, onEngine && engine.rate ? `${exact(engine.rate)} Hz` : null) },
		{ label: t('play.connection'), value: onEngine && engine.bandwidth ? mbits(engine.bandwidth) : '' }
	].filter((row) => row.value));

	function sample() {
		if (!video) return;
		const q = video.getVideoPlaybackQuality?.();
		if (q) quality = { dropped: q.droppedVideoFrames, total: q.totalVideoFrames };
		const end = video.buffered.length ? video.buffered.end(video.buffered.length - 1) : 0;
		buffered = Math.max(0, end - video.currentTime);
		decoded = video.videoWidth ? size(video.videoWidth, video.videoHeight) : '';
	}

	async function askServer() {
		// the panel says a dash where the box did not answer
		server = await request<typeof server>('/api/play/stats', {}, { failed: () => {} });
	}

	$effect(() => {
		if (opened) askServer();
	});

	$effect(() => {
		sample();
		const beat = setInterval(() => {
			sample();
			if (opened) askServer();
		}, 2000);
		return () => clearInterval(beat);
	});
</script>

<aside class="info" class:opened data-info>
	<div class="story">
		<h2>{plan.title}</h2>
		{#if facts}<p class="facts">{facts}</p>{/if}
		<Clamped text={plan.details?.overview ?? ''} bind:opened beyond class="overview" data-more />
	</div>
	<dl class="now">
		{#each now as row (row.label)}
			<div>
				<dt>{row.label}</dt>
				<dd>{row.value}</dd>
			</div>
		{/each}
	</dl>
	{#if opened}
		{#if plan.details?.cast?.length}
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
		<div class="detail">
			<div>
				<h3>{t('play.server')}</h3>
				<dl>
					<dt>{t('play.sent')}</dt>
					<dd>{onEngine && !rebuilt ? t('play.untouched') : plan.mode}</dd>
					<dt>{t('play.target')}</dt>
					<dd>
						{onEngine && !rebuilt
							? t('play.noResize')
							: plan.width && plan.height
								? size(plan.width, plan.height)
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
							{plan.codec ?? 'h264'} · {t('play.hardware')}
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
						<dt>{t('play.stalls')}</dt>
						<dd>{formatNumber(engine.stalls)}</dd>
					{:else}
						<dt>{t('play.buffered')}</dt>
						<dd>{buffered ? `${formatNumber(buffered, { maximumFractionDigits: 0 })} s` : '—'}</dd>
					{/if}
				</dl>
			</div>
		</div>
	{/if}
</aside>

<style>
	.info {
		padding: 0.9rem 1.1rem 1.1rem;
		background: var(--bg);
		color: color-mix(in srgb, var(--text) 85%, var(--bg));
		font-size: var(--fs-s);
		border-top: 1px solid var(--border);
	}
	/* opened, it is read rather than glanced at: as much of the screen as it
	   needs, and a remote walks it a page at a time */
	.info.opened {
		max-height: 85vh;
		overflow-y: auto;
	}
	.story {
		--lines: 2;
	}
	.story h2 {
		margin: 0;
		font-size: var(--fs-2xl);
		font-weight: 600;
		color: var(--bright, var(--text));
	}
	.facts {
		margin: 0.25rem 0 0;
		color: var(--muted);
	}
	.story :global(.overview) {
		margin: 0.6rem 0 0;
		max-width: 62ch;
		font-size: var(--fs-l);
		line-height: 1.5;
		color: var(--text);
	}
	.story :global(.more) {
		font-size: var(--fs-m);
	}
	.now {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 2rem;
		margin: 0.9rem 0 0;
		font-size: var(--fs-m);
		font-variant-numeric: tabular-nums;
	}
	.now div {
		display: flex;
		gap: 0.5rem;
	}
	.now dt {
		color: var(--muted);
	}
	.now dd {
		margin: 0;
		color: var(--text);
	}
	.cast {
		display: flex;
		gap: 1rem;
		margin: 1.1rem 0 0;
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
	.detail {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr));
		gap: 1.5rem;
		margin-top: 1.1rem;
	}
	.detail h3 {
		margin: 0 0 0.5rem;
		font-size: var(--fs-xs);
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.detail dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.3rem 0.9rem;
		margin: 0;
	}
	.detail dt {
		color: var(--muted);
	}
	.detail dd {
		margin: 0;
		font-variant-numeric: tabular-nums;
	}
</style>
