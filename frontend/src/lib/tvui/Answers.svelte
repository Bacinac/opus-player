<script lang="ts" module>
	export type Answer = {
		key: string;
		label: string;
		/** what the answer is, said smaller — a country under a town */
		note?: string | null;
	};
</script>

<script lang="ts">
	// Four answers, two by two.
	//
	// Two by two because that is what a D-pad is: up, down, left and right land
	// on one answer each, with nothing to walk past on the way. A column of four
	// would be three presses to the last one, and the clock is running.
	//
	// Marking is the same in both directions: the right one lights whether or
	// not it was pressed, and the one pressed in error is marked as well. A
	// screen that only lit the mistake would leave somebody who ran out of time
	// never told what it was.
	//
	// A marked answer is not disabled. A disabled button cannot hold the ring,
	// and a remote sitting on one has no arrows left — so the press goes on
	// being a press and the screen above decides it no longer means anything.

	let {
		options,
		chosen = null,
		correct = null,
		revealed = false,
		onpick
	}: {
		options: Answer[];
		/** what was pressed, once something was */
		chosen?: string | null;
		/** which one was right — only meaningful once revealed */
		correct?: string | null;
		revealed?: boolean;
		onpick?: (key: string) => void;
	} = $props();
</script>

<div class="answers" class:revealed>
	{#each options as option (option.key)}
		<button
			class="answer"
			class:right={revealed && option.key === correct}
			class:wrong={revealed && option.key === chosen && option.key !== correct}
			class:faded={revealed && option.key !== correct && option.key !== chosen}
			onclick={() => onpick?.(option.key)}
		>
			<span class="what">
				<span class="label">{option.label}</span>
				{#if option.note}<span class="note">{option.note}</span>{/if}
			</span>
		</button>
	{/each}
</div>

<style>
	.answers {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0.75rem;
	}
	.answer {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		min-height: 3.4rem;
		padding: 0.6rem 1rem;
		font: inherit;
		text-align: left;
		color: var(--text);
		background: var(--card-ground, color-mix(in srgb, var(--bg) 62%, transparent));
		border: var(--card-line, 1px solid color-mix(in srgb, var(--text) 12%, transparent));
		border-radius: var(--radius-l, 14px);
		cursor: pointer;
		transition:
			background 0.12s ease,
			border-color 0.12s ease;
	}
	.answers:not(.revealed) .answer:hover {
		border-color: var(--accent);
	}
	.answer:focus-visible {
		outline: var(--focus-ring, 3px solid var(--accent));
		outline-offset: 2px;
	}
	.revealed .answer {
		cursor: default;
	}
	.what {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.note {
		color: var(--muted);
		font-size: 0.8em;
	}

	/* The marking. Green is the answer, red is what was pressed instead — and
	   the two it was not is dimmed rather than hidden, because the four are
	   still what the question offered. */
	.right {
		background: color-mix(in srgb, var(--ok) 30%, transparent);
		border-color: var(--ok);
		color: var(--bright, var(--text));
	}
	.wrong {
		background: color-mix(in srgb, var(--danger) 26%, transparent);
		border-color: var(--danger);
	}
	.faded {
		opacity: 0.45;
	}

	/* One column on a television: they stand in a rail beside the picture now,
	   not in a block under it, and two of them side by side in that width are
	   two truncated names. Shorter boxes with it — at 4.6rem four of them were
	   a wall, and the height they took came off the photograph. */
	:global(html.tv) .answers {
		grid-template-columns: 1fr;
		gap: 0.8rem;
	}
	:global(html.tv) .answer {
		min-height: 3.4rem;
		padding: 0.6rem 1.2rem;
		font-size: var(--fs-xl);
	}

	/* One hand, one column: at this width two answers side by side are two
	   truncated names. */
	@media (max-width: 26rem) {
		.answers {
			grid-template-columns: 1fr;
		}
	}
</style>
