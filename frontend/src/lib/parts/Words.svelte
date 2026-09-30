<script lang="ts">
	// The words to what is playing, wherever they are asked for.
	//
	// They belonged to the record's own screen, which meant they could only be
	// read while that screen was open. They are asked for from the bar now — the
	// one thing that is on every screen — and drawn over whatever is underneath.
	//
	// A line with a time on it is a place in the song: pressing it goes there.

	import { t } from '$lib/i18n';
	import Press from '$lib/tvui/Press.svelte';
	import { lyrics, type LyricsState } from '$lib/keep/lyrics.svelte';
	import { cast } from '$lib/keep/cast.svelte';
	import { surface } from '$lib/keep/surface.svelte';

	let {
		elapsed = 0,
		seek,
		reading = lyrics
	}: {
		elapsed?: number;
		seek: (to: number) => void;
		/** whose words: the bar reads what is playing, a record's page reads the
		    song the remote is standing on */
		reading?: LyricsState;
	} = $props();

	// nothing can be moved through on a device that plays its own queue
	const seekable = $derived(!cast.casting);
	const line = $derived(reading.at(elapsed));

	/** Words nobody timed are read rather than followed. Verse by verse, which
	 *  is how the text is written anyway, and what lets the column be scrolled
	 *  a screenful at a time rather than a paragraph at a time. */
	const stanzas = $derived(
		(reading.words?.plain ?? '').split(/\n\s*\n/).map((one) => one.trim()).filter(Boolean)
	);

	let words = $state<HTMLElement | null>(null);

	// A timed lyric is a column of places in the song and the ring walks it. An
	// untimed one has nothing to land on, and on this surface the arrows move
	// the ring and never the page — so it could not be scrolled at all. The
	// arrows read further instead, which is what the reading screen does with a
	// long description for the same reason.
	$effect(() => {
		if (!surface.isTv || reading.timed) return;
		const onkey = (event: KeyboardEvent) => {
			if (!words?.isConnected || !words.clientHeight) return;
			if (event.key === 'ArrowDown') words.scrollBy({ top: words.clientHeight * 0.6 });
			else if (event.key === 'ArrowUp') words.scrollBy({ top: -words.clientHeight * 0.6 });
			else return;
			event.preventDefault();
		};
		window.addEventListener('keydown', onkey, true);
		return () => window.removeEventListener('keydown', onkey, true);
	});

	// the line being sung is brought to the middle, so reading along never means
	// following the words off the bottom of the screen
	// scrolled by hand: scrollIntoView moves every scrolling ancestor too, and
	// a fixed sleeve with its overflow hidden is one — its header went off the
	// top of the screen and stayed there
	$effect(() => {
		if (!words || line < 0) return;
		const sung = words.querySelector<HTMLElement>(`[data-line="${line}"]`);
		if (!sung) return;
		const by = sung.getBoundingClientRect().top - words.getBoundingClientRect().top;
		words.scrollTo({
			top: words.scrollTop + by - (words.clientHeight - sung.offsetHeight) / 2,
			behavior: 'smooth'
		});
	});
</script>

<div class="words" bind:this={words}>
	{#if reading.loading}
		<p class="quiet">{t('sleeve.looking')}</p>
	{:else if reading.failed}
		<p class="quiet">{t('sleeve.wordsUnreachable')}</p>
		{#if reading.trackId !== null}
			<div class="again">
				<Press onclick={() => reading.load(reading.trackId, true)}>{t('sleeve.lookAgain')}</Press>
			</div>
		{/if}
	{:else if reading.timed}
		{#each reading.words!.lines as l, i (i)}
			{#if l.text}
				<button
					class="line"
					class:now={i === line}
					class:past={i < line}
					data-line={i}
					disabled={!seekable}
					onclick={(e) => (e.stopPropagation(), seek(l.at))}
				>
					{l.text}
				</button>
			{:else}
				<div class="gap" class:now={i === line} data-line={i}>{i === line ? '♪' : ''}</div>
			{/if}
		{/each}
	{:else if reading.words?.plain}
		{#each stanzas as verse, i (i)}
			<p class="plain">{verse}</p>
		{/each}
	{:else if reading.words?.instrumental}
		<p class="quiet">{t('sleeve.instrumental')}</p>
	{:else if !reading.known}
		<p class="quiet">{t('sleeve.notOurs')}</p>
	{:else}
		<p class="quiet">{t('sleeve.noWords')}</p>
	{/if}
</div>

<style>
	/* Held to a measure and centred in whatever room there is: a line of a song
	   stretched across a wide screen is a line nobody finds the start of twice.
	   It fades at both ends rather than stopping, so a column that carries on
	   reads as one that carries on. */
	.words {
		display: flex;
		flex-direction: column;
		justify-content: safe center;
		min-height: 0;
		overflow-y: auto;
		scrollbar-width: none;
		font-size: var(--fs-xl);
		line-height: 1.75;
		mask-image: linear-gradient(to bottom, transparent, black 6%, black 94%, transparent);
	}
	.words::-webkit-scrollbar {
		display: none;
	}
	.words > :global(*) {
		width: min(100%, 46ch);
		margin-inline: auto;
	}
	.line {
		display: block;
		border: none;
		background: transparent;
		color: var(--muted);
		font: inherit;
		font-size: var(--fs-xl);
		line-height: 1.5;
		text-align: left;
		padding: 0.3rem 0.5rem;
		border-radius: 6px;
		cursor: pointer;
		transition: color 140ms ease;
	}
	.line:disabled {
		cursor: default;
	}
	.line.past {
		opacity: 0.45;
	}
	.line.now {
		color: var(--bright, inherit);
		font-weight: 600;
		opacity: 1;
	}
	.line:hover:not(:disabled),
	.line:focus-visible {
		background: color-mix(in srgb, currentColor 12%, transparent);
	}
	.gap {
		height: 1.1rem;
		color: var(--muted);
		font-size: var(--fs-l);
		line-height: 1.1rem;
		padding-left: 0.5rem;
	}
	.gap.now {
		color: inherit;
	}
	.plain {
		margin: 0;
		scroll-margin-block: 2rem;
		white-space: pre-wrap;
		font-size: var(--fs-xl);
		line-height: 1.6;
		color: color-mix(in srgb, currentColor 80%, transparent);
	}
	.plain + .plain {
		margin-top: 1rem;
	}

	.quiet {
		color: var(--muted);
	}
	.again {
		margin-top: 0.6rem;
	}
</style>
