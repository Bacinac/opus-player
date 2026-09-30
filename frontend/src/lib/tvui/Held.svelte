<script lang="ts">
	// Something standing over the screen, and everything that follows from that.
	//
	// Four things a component would otherwise have to remember separately, and
	// would forget separately: mark the region so the arrows stay inside it,
	// register a rung so BACK closes this and not the page behind it, put the
	// remote on something when it opens, and stop the page underneath scrolling.
	// A menu with the first and not the second lets BACK go straight through it
	// and navigate while it stays on screen.
	//
	// One component, so a thing that takes the screen cannot take only part of it.

	import type { Snippet } from 'svelte';
	import { onBack } from '$lib/keep/back.svelte';
	import { surface } from '$lib/keep/surface.svelte';

	let {
		onclose,
		first = '',
		still = true,
		layer = 'over',
		children
	}: {
		/** what BACK does here. Returning false lets the press fall through to
		 *  whatever is under this, which is what a thing that cannot be closed
		 *  should do rather than swallowing the key. */
		onclose?: () => boolean | void;
		/** what takes the remote when this opens; the first focusable otherwise */
		first?: string;
		/** whether the page underneath is stopped from scrolling */
		still?: boolean;
		/** which shelf of the stacking order this stands on */
		layer?: 'over' | 'stage' | 'watch';
		children: Snippet;
	} = $props();

	let box = $state<HTMLElement>();

	$effect(() =>
		onBack(() => {
			if (!onclose) return false;
			return onclose() !== false;
		})
	);

	$effect(() => {
		if (!box || !surface.isTv) return;
		// after the frame it was mounted in: the thing that opens is built by the
		// same flush that mounts this, so asking now finds a box with nothing in it
		const at = requestAnimationFrame(() => {
			const want = first ? box?.querySelector<HTMLElement>(first) : null;
			const any = box?.querySelector<HTMLElement>(
				'a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])'
			);
			(want ?? any)?.focus({ preventScroll: true });
		});
		return () => cancelAnimationFrame(at);
	});

	$effect(() => {
		if (!still) return;
		const was = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		return () => {
			document.body.style.overflow = was;
		};
	});
</script>

<div bind:this={box} class="held" data-holds-remote style:--held-layer="var(--z-{layer})">
	{@render children()}
</div>

<style>
	.held {
		z-index: var(--held-layer, 24);
	}
</style>
