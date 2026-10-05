<script lang="ts">
	import { duration } from '$lib/i18n';
	// The controls, wherever something is playing.
	//
	// There were three of these — the bar along the bottom, the record full
	// screen, and the film's own overlay — with the same keys in three orders,
	// three sizes and three ideas of where the clock goes. A person who has
	// learned one of them has learned all of them now: keys first, then where
	// you are, the bar, and how long it runs. What differs between a film and a
	// song is what each of them adds at the end, and that is what `extras` is.

	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';
	import { Icon } from '$lib/kit';
	import Press from '$lib/tvui/Press.svelte';

	let {
		position,
		total,
		going,
		toggle,
		seek,
		prev,
		next,
		hasNext = true,
		seekable = true,
		/** The controls, and not the position among them: a remote walking the bar
		 *  wants play, the words, the languages. A line between two keys is a
		 *  stop nobody meant to make — and once it is made, left and right belong
		 *  to the slider and there is no way off it, which is how the key beside
		 *  it became unreachable. */
		barFocusable = true,
		small = false,
		ends = '',
		extras
	}: {
		position: number;
		total: number;
		going: boolean;
		toggle: () => void;
		seek: (to: number) => void;
		prev?: () => void;
		next?: () => void;
		hasNext?: boolean;
		seekable?: boolean;
		barFocusable?: boolean;
		small?: boolean;
		/** when what is playing will be over, as the clock will read then */
		ends?: string;
		extras?: Snippet;
	} = $props();

	// how much of it has gone, for the line to be drawn in two colours: a track
	// styled by hand loses the browser's own filling, and a bar that does not
	// show where you are is a bar that says nothing
	const glyph = $derived(small ? 16 : 20);

	// Where a finger holding the line has taken it. The seek happens when it lets
	// go: a film seeks by asking for a new stream, and seeking on every step of a
	// drag asked for thirty of them in a second, until one failed and the
	// television gave the film up.
	let held = $state<number | null>(null);
	const shown = $derived(held ?? position);

	function letGo(to: number) {
		held = null;
		seek(to);
	}

	// a drag that ends where it began fires no change, and the line would stay
	// held there while the film ran on; after the change, if there is one
	function released() {
		setTimeout(() => (held = null));
	}

	const done = $derived(
		total > 0 ? Math.min(100, Math.max(0, (shown / total) * 100)) : 0
	);
</script>

<div class="transport" class:small>
	{#if prev}
		<Press tone="key" data-control="previous" onclick={prev} label={t('queue.previous')}>
			<Icon name="previous" size={glyph} />
		</Press>
	{/if}
	<Press tone="key" data-control="toggle" onclick={toggle} label={t(going ? 'queue.pause' : 'card.play')}>
		<Icon name={going ? 'pause' : 'play'} size={glyph + 4} />
	</Press>
	{#if next}
		<Press tone="key" data-control="next" onclick={next} disabled={!hasNext} label={t('queue.next')}>
			<Icon name="next" size={glyph} />
		</Press>
	{/if}
	{#if ends}
		<span class="ends">{t('play.ends', { time: ends })}</span>
	{/if}

	<span class="time">{duration(shown)}</span>
	<input
		type="range"
		data-position
		style={`--done:${done}%`}
		min="0"
		max={total || 0}
		value={shown}
		oninput={(e) => (held = Number((e.currentTarget as HTMLInputElement).value))}
		onchange={(e) => letGo(Number((e.currentTarget as HTMLInputElement).value))}
		onpointerup={released}
		onpointercancel={() => (held = null)}
		disabled={!seekable}
		tabindex={barFocusable ? 0 : -1}
		aria-label={t('queue.position')}
	/>
	<span class="time">{duration(total)}</span>

	{#if extras}{@render extras()}{/if}
</div>

<style>
	.transport {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		min-width: 0;
	}
	.time {
		font-variant-numeric: tabular-nums;
		font-size: 0.85em;
		color: var(--muted);
		/* wide enough for the digit a film gains at ten minutes, so the bar does
		   not step sideways once a second */
		min-width: 3.4rem;
		text-align: center;
	}
	.small .time {
		min-width: 2.9rem;
	}
	.ends {
		font-variant-numeric: tabular-nums;
		font-size: 0.85em;
		color: var(--muted);
		white-space: nowrap;
	}
	/* A hairline the width of the screen, in the colour of what is playing —
	   the same weight as the rules and borders everything else on this surface
	   is drawn with. The browser's own slider is a fat bright pill and reads as
	   a control from a different application. */
	input {
		flex: 1;
		min-width: 0;
		-webkit-appearance: none;
		appearance: none;
		height: 1.1rem;
		margin: 0;
		padding: 0;
		border: none;
		background: transparent;
		cursor: pointer;
	}
	input:disabled {
		opacity: 0.5;
		cursor: default;
	}
	input::-webkit-slider-runnable-track {
		height: 3px;
		border-radius: 999px;
		background: linear-gradient(
			to right,
			var(--accent) var(--done, 0%),
			color-mix(in srgb, currentColor 20%, transparent) var(--done, 0%)
		);
	}
	input::-moz-range-track {
		height: 3px;
		border-radius: 999px;
		background: linear-gradient(
			to right,
			var(--accent) var(--done, 0%),
			color-mix(in srgb, currentColor 20%, transparent) var(--done, 0%)
		);
	}
	input::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 9px;
		height: 9px;
		margin-top: -3px;
		border: none;
		border-radius: 50%;
		background: var(--accent);
	}
	input::-moz-range-thumb {
		width: 9px;
		height: 9px;
		border: none;
		border-radius: 50%;
		background: var(--accent);
	}
	input:focus-visible::-webkit-slider-thumb {
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 35%, transparent);
	}
	input:focus-visible::-moz-range-thumb {
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 35%, transparent);
	}
</style>
