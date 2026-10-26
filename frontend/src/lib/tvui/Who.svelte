<script lang="ts">
	// A person as a pill: their name in their colour. One drawing of it, so a
	// room's answers, a lobby and a table of scores all show the same person
	// the same way.
	import type { Snippet } from 'svelte';

	let {
		name,
		colour = '',
		tone = null,
		children
	}: {
		name: string;
		colour?: string;
		/** marked right or wrong, where an answer is being shown */
		tone?: 'hit' | 'miss' | null;
		children?: Snippet;
	} = $props();
</script>

<span class="who" class:hit={tone === 'hit'} class:miss={tone === 'miss'} style:--who={colour || 'var(--accent)'}>
	{name}{@render children?.()}
</span>

<style>
	.who {
		display: inline-flex;
		align-items: baseline;
		gap: 0.3rem;
		padding: 0.1rem 0.6rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--who) 30%, transparent);
		border: 1px solid var(--who);
		font-size: 0.85em;
		white-space: nowrap;
	}
	.hit {
		border-color: var(--ok);
		background: color-mix(in srgb, var(--ok) 30%, transparent);
	}
	.miss {
		opacity: 0.6;
	}
	:global(html.tv) .who {
		font-size: var(--fs-l);
	}
</style>
