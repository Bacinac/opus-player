<script lang="ts">
	// What is left of the twenty seconds, as a ring that empties.
	//
	// A ring rather than a number: from the sofa a number has to be read, and a
	// ring is seen. The number is inside it all the same, because at three
	// seconds left "three" is what somebody wants.
	//
	// It runs off the clock, not off a frame counter. A tab that was hidden and
	// came back, or a television that dropped frames, must not end up believing
	// there is more time left than there is — the server is timing this and
	// would disagree.

	let {
		until,
		seconds,
		running = true
	}: {
		/** when the time is up, as epoch milliseconds */
		until: number;
		/** how long the whole question was given, for the ring's proportion */
		seconds: number;
		running?: boolean;
	} = $props();

	let now = $state(Date.now());

	$effect(() => {
		if (!running) return;
		const beat = setInterval(() => (now = Date.now()), 100);
		return () => clearInterval(beat);
	});

	const left = $derived(Math.max(0, (until - now) / 1000));
	const part = $derived(Math.max(0, Math.min(1, left / seconds)));
	// the last five are what the ring is for
	const urgent = $derived(running && left <= 5);
	const R = 22;
	const ROUND = 2 * Math.PI * R;
</script>

<div class="clock" class:urgent>
	<svg viewBox="0 0 52 52" aria-hidden="true">
		<circle class="track" cx="26" cy="26" r={R} />
		<circle
			class="left"
			cx="26"
			cy="26"
			r={R}
			stroke-dasharray={ROUND}
			stroke-dashoffset={ROUND * (1 - part)}
		/>
	</svg>
	<span class="count">{Math.ceil(left)}</span>
</div>

<style>
	.clock {
		position: relative;
		width: 3.25rem;
		height: 3.25rem;
		flex: 0 0 auto;
	}
	svg {
		width: 100%;
		height: 100%;
		/* start at the top and empty clockwise, which is the direction a clock
		   is read in even when it has no hands */
		transform: rotate(-90deg);
	}
	circle {
		fill: none;
		stroke-width: 4;
		stroke-linecap: round;
	}
	.track {
		stroke: color-mix(in srgb, var(--text) 18%, transparent);
	}
	.left {
		stroke: var(--accent);
		transition: stroke-dashoffset 0.1s linear;
	}
	.count {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		font-variant-numeric: tabular-nums;
		font-weight: 600;
		color: var(--text);
	}
	.urgent .left,
	.urgent .count {
		stroke: var(--danger);
		color: var(--danger);
	}
	.urgent .count {
		animation: beat 1s steps(2, end) infinite;
	}
	@keyframes beat {
		50% {
			opacity: 0.35;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.urgent .count {
			animation: none;
		}
	}

	:global(html.tv) .clock {
		width: 4.25rem;
		height: 4.25rem;
		font-size: var(--fs-xl);
	}
</style>
