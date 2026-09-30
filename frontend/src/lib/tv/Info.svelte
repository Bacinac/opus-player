<script lang="ts">
	// Everything about the thing on the screen that the screen itself does not
	// say: the whole description, what this copy of it is, who made it. The page
	// keeps a name, one line and one thing to do; this is where the rest went.

	import type { Snippet } from 'svelte';
	import { onBack } from '$lib/keep/back.svelte';

	let {
		open = $bindable(false),
		title,
		overview = '',
		remote = true,
		side = false,
		children
	}: {
		open?: boolean;
		title: string;
		overview?: string;
		/** whether the remote's INFO key opens this: one window on a page may */
		remote?: boolean;
		/** a panel beside the page, for asking something, rather than a page of reading */
		side?: boolean;
		children?: Snippet;
	} = $props();

	let body = $state<HTMLElement | null>(null);
	let from: HTMLElement | null = null;

	// What is in here to press — a director, where this copy came from — takes
	// the ring and the arrows walk it. When there is nothing, the ring is put
	// down and the arrows read further instead; either way it is given back
	// where it was when this closes.
	let walks = false;
	$effect(() => {
		if (!open || !body) return;
		from = document.activeElement as HTMLElement | null;
		const first = body.querySelector<HTMLElement>('button:not([disabled]), a[href]');
		walks = Boolean(first);
		if (first) first.focus({ preventScroll: true });
		else from?.blur();
		return () => {
			from?.focus({ preventScroll: true });
			from = null;
		};
	});

	// Everything on one screen: a long biography is set smaller until it fits
	// rather than scrolled through ten feet away.
	const LARGEST = 1.05;
	const SMALLEST = 0.8;
	$effect(() => {
		void overview;
		if (!open || side || !body) return;
		const page = body;
		let size = LARGEST;
		page.style.setProperty('--info-size', `${size}rem`);
		while (page.scrollHeight > page.clientHeight + 1 && size > SMALLEST) {
			size = Math.round((size - 0.05) * 100) / 100;
			page.style.setProperty('--info-size', `${size}rem`);
		}
	});

	$effect(() =>
		onBack(
			() => {
				if (!open) return false;
				open = false;
				return true;
			},
			() => open
		)
	);

	// A remote's INFO key, where it has one, opens and closes this the way the
	// button beside the page's name does.
	$effect(() => {
		const onkey = (event: KeyboardEvent) => {
			if (event.key === 'Info' && remote) open = !open;
			else if (!open || walks) return;
			else if (event.key === 'ArrowDown') body?.scrollBy({ top: body.clientHeight * 0.6 });
			else if (event.key === 'ArrowUp') body?.scrollBy({ top: -body.clientHeight * 0.6 });
			else if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
			event.preventDefault();
		};
		window.addEventListener('keydown', onkey, true);
		return () => window.removeEventListener('keydown', onkey, true);
	});
</script>

{#if open}
	<div class="info" data-holds-remote role="presentation" onclick={() => (open = false)}>
		<aside bind:this={body} class:side aria-label={title} onclick={(e) => e.stopPropagation()} role="presentation">
			<h1>{title}</h1>
			{#if overview}<p class="overview">{overview}</p>{/if}
			{#if children}<div class="facts">{@render children()}</div>{/if}
		</aside>
	</div>
{/if}

<style>
	.info {
		position: fixed;
		inset: 0;
		z-index: var(--z-info, 32);
		background: color-mix(in srgb, var(--bg) 55%, transparent);
	}
	/* Reading is done across the screen: a column a third of the screen wide
	   made a paragraph a scroll. Opaque, because the page's own title showing
	   through behind this one reads as two titles. */
	aside {
		position: absolute;
		inset: 0;
		box-sizing: border-box;
		padding: var(--tenfoot-pad, 3rem) calc(var(--tenfoot-pad, 3rem) * 2)
			calc(var(--tv-bar-h, 0px) + var(--tenfoot-safe-y, 1.7rem));
		background: var(--bg);
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 1.1rem;
	}
	aside.side {
		inset: 0 0 0 auto;
		width: min(52%, 34rem);
		padding: var(--tenfoot-pad, 3rem) var(--tenfoot-pad, 3rem)
			calc(var(--tv-bar-h, 0px) + var(--tenfoot-safe-y, 1.7rem));
		background: var(--surface);
		border-left: 1px solid var(--border);
		gap: 1rem;
	}
	h1 {
		margin: 0;
		font-size: 2rem;
		line-height: 1.1;
	}
	aside.side h1 {
		font-size: var(--head-title, var(--fs-2xl));
	}
	.overview {
		margin: 0;
		font-size: var(--info-size, var(--fs-l));
		line-height: 1.5;
		white-space: pre-line;
	}
	aside.side .overview {
		font-size: var(--fs-l);
	}
	.facts {
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
	}
</style>
