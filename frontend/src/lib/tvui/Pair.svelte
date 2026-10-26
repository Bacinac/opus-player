<script lang="ts">
	// Two photographs, lettered. Which was taken first is answered by pressing
	// one, so each picture is the button — side by side on a wide screen, one
	// above the other in a hand, and lettered rather than called "left" and
	// "right" because of that.
	import type { Picture, Someone } from '#lib/ask/guess.js';
	import { previewOf } from '#lib/opus/index.js';
	import Who from '#lib/tvui/Who.svelte';

	let {
		a,
		b,
		chosen = null,
		correct = null,
		revealed = false,
		facts = null,
		marks = {},
		onpick
	}: {
		a: Picture;
		b: Picture;
		chosen?: string | null;
		correct?: string | null;
		revealed?: boolean;
		/** what each turned out to be, under it once revealed */
		facts?: { a: string; b: string } | null;
		/** who pressed which, once revealed */
		marks?: Record<string, Someone[]>;
		onpick?: (key: string) => void;
	} = $props();

	const sides = $derived([
		{ key: 'a', letter: 'A', photo: a, said: facts?.a },
		{ key: 'b', letter: 'B', photo: b, said: facts?.b }
	]);
</script>

<div class="pair" class:revealed>
	{#each sides as side (side.key)}
		<button
			class="side"
			class:right={revealed && side.key === correct}
			class:wrong={revealed && side.key === chosen && side.key !== correct}
			class:faded={revealed && side.key !== correct && side.key !== chosen}
			onclick={() => onpick?.(side.key)}
		>
			<img src={previewOf(side.photo.id, side.photo.turn)} alt="" />
			<span class="letter">{side.letter}</span>
			{#if revealed && (side.said || marks[side.key]?.length)}
				<span class="under">
					{#if side.said}<span class="said">{side.said}</span>{/if}
					{#each marks[side.key] ?? [] as who (who.key)}
						<Who name={who.name} colour={who.colour} />
					{/each}
				</span>
			{/if}
		</button>
	{/each}
</div>

<style>
	.pair {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		flex: 1 1 auto;
		min-height: 0;
	}
	.side {
		position: relative;
		display: block;
		min-height: 0;
		min-width: 0;
		padding: 0;
		font: inherit;
		color: var(--text);
		background: var(--card-ground, color-mix(in srgb, var(--bg) 62%, transparent));
		border: var(--card-line, 1px solid color-mix(in srgb, var(--text) 12%, transparent));
		border-radius: var(--radius-l, 14px);
		overflow: hidden;
		cursor: pointer;
		transition: border-color 0.12s ease;
	}
	.pair:not(.revealed) .side:hover {
		border-color: var(--accent);
	}
	.side:focus-visible {
		outline: var(--focus-ring, 3px solid var(--accent));
		outline-offset: 2px;
	}
	.revealed .side {
		cursor: default;
	}
	.side img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
	.letter {
		position: absolute;
		top: 0.6rem;
		left: 0.6rem;
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 50%;
		background: color-mix(in srgb, var(--bg) 80%, transparent);
		font-weight: 700;
	}
	.under {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 0.6rem;
		align-items: center;
		padding: 0.4rem 0.7rem;
		background: color-mix(in srgb, var(--bg) 80%, transparent);
		font-size: 0.9em;
		text-align: left;
	}
	.said {
		color: var(--muted);
	}
	.right {
		border-color: var(--ok);
		box-shadow: inset 0 0 0 3px var(--ok);
	}
	.wrong {
		border-color: var(--danger);
		box-shadow: inset 0 0 0 3px var(--danger);
	}
	.faded {
		opacity: 0.45;
	}
	:global(html.tv) .pair {
		grid-area: stage;
		gap: 1.2rem;
	}
	:global(html.tv) .letter {
		width: 3rem;
		height: 3rem;
		font-size: var(--fs-xl);
	}
	/* one hand: one above the other, since two landscapes side by side in a
	   phone's width are two thumbnails */
	@media (max-width: 560px) and (orientation: portrait) {
		.pair {
			grid-template-columns: 1fr;
			grid-template-rows: 1fr 1fr;
		}
	}
</style>
