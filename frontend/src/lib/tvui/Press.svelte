<script lang="ts">
	// Every button on this surface, in the five shapes a button here actually
	// takes. Five because five are drawn — counted, not designed: each shape
	// takes the padding, border and font size its family already agreed on most.
	//
	//   go     the one thing this screen wants pressed — accent-filled
	//   plain  a thing that may be pressed — outlined, quiet
	//   pill   a chip in a row of chips; `on` marks the one in force
	//   bare   a word that happens to be pressable
	//   key    a transport key: no box until the remote lands on it
	//
	// Size is deliberately NOT a prop — it falls out of html.tv, so a screen
	// cannot order a bigger button for itself.

	import type { Snippet } from 'svelte';

	let {
		tone = 'plain',
		type = 'button',
		on = false,
		refused = false,
		disabled = false,
		title,
		label,
		onclick,
		onfocus,
		children,
		...marks
	}: {
		tone?: 'go' | 'plain' | 'pill' | 'bare' | 'key';
		type?: 'button' | 'submit';
		/** the one in force — a chooser's chosen, a view's current */
		on?: boolean;
		/** the one held out — a filter's "everything but this" */
		refused?: boolean;
		disabled?: boolean;
		title?: string;
		label?: string;
		onclick?: (event: MouseEvent) => void;
		onfocus?: (event: FocusEvent) => void;
		children: Snippet;
		/** what the remote finds a control by: data-control, data-menu */
		[mark: `data-${string}`]: string | boolean | undefined;
	} = $props();
</script>

<button {...marks} class="press {tone}" class:on class:refused {type} {disabled} {title} aria-label={label} {onclick} {onfocus}>
	{@render children()}
</button>

<style>
	.press {
		font: inherit;
		/* Quiet, not dead. This was the muted grey, which is the same grey a
		   control wears when it cannot be pressed — so "Dalje", the one thing to
		   press after answering, read as refused. Being unavailable is said by
		   the opacity below, and only by that. */
		color: var(--text);
		background: transparent;
		border: 1px solid var(--border);
		border-radius: var(--radius-s, 8px);
		padding: 0.5rem 1.4rem;
		cursor: pointer;
	}
	.press:disabled {
		/* 0.5, the median of the three in use — at 0.35 a disabled key is
		   invisible at ten feet */
		opacity: 0.5;
		cursor: default;
	}

	.go {
		/* its own colour rather than no border at all: dropping it made a chosen
		   button two pixels shorter than the one beside it, so a row of them sat
		   crooked and each one jumped as it was chosen */
		border-color: var(--accent);
		background: var(--accent);
		color: var(--bg);
		font-weight: 600;
	}
	/* the primary button is accent-filled, so an accent ring around it is the
	   one case where the ring says nothing: it lifts instead */
	.go:focus-visible {
		outline: none;
		background: color-mix(in srgb, var(--accent) 80%, var(--bright, var(--text)));
	}

	/* Across a room a lift of twenty percent is not a signal — Play simply did
	   not look chosen. The ring comes back on a television, drawn in the text's
	   colour rather than the accent so that it reads against the fill it
	   surrounds, and on :focus as well: a remote in a WebView does not always
	   satisfy :focus-visible, and a mark that hangs on it alone is a mark that
	   sometimes is not there. */
	:global(html.tv) .go:focus,
	:global(html.tv) .go:focus-visible {
		outline: 3px solid var(--text);
		outline-offset: 3px;
		background: var(--accent);
	}

	.pill {
		padding: 0.25rem 0.7rem;
		border-radius: var(--radius-pill);
	}
	.pill.on {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--bg);
	}
	.pill:hover {
		border-color: var(--accent);
	}
	/* held out, and not merely not chosen: the mark goes grey and a line is
	   struck through it, so it cannot be mistaken for a pill at rest */
	.pill.refused {
		position: relative;
		color: var(--muted);
		border-style: dashed;
	}
	.pill.refused :global(img) {
		filter: grayscale(1);
		opacity: 0.45;
	}
	.pill.refused::after {
		content: '';
		position: absolute;
		left: 10%;
		right: 10%;
		top: calc(50% - 1px);
		border-top: 2px solid var(--danger);
		transform: rotate(-24deg);
		pointer-events: none;
	}

	/* a word gets padding for the wash to live in, paid back outside so the
	   word still sits flush with the text around it */
	.bare {
		border: none;
		border-radius: var(--radius-pill);
		padding: 0.1rem 0.4rem;
		margin: -0.1rem -0.4rem;
	}
	/* a ring around a word inside running text underlines nothing — the wash
	   is the one sanctioned alternative, and this is its one home */
	.bare:focus-visible {
		outline: none;
		background: color-mix(in srgb, var(--accent) 25%, transparent);
	}

	.key {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: none;
		padding: 0.4rem 0.6rem;
		color: inherit;
		line-height: 1;
		white-space: nowrap;
	}
	/* no box, so what a key has instead is a wash under whatever is on it */
	.key:hover:not(:disabled),
	.key:focus-visible {
		background: color-mix(in srgb, currentColor 12%, transparent);
	}

	/* Bigger than a desk's, smaller than the menu. At 1.15rem a row of ways was
	   five buttons the size of the sections beside them, which reads as five more
	   sections. What has to be legible across a room is the word, not the box
	   around it. */
	:global(html.tv) .press {
		font-size: var(--fs-l);
	}
	:global(html.tv) .press:not(.key) {
		padding: 0.35rem 1rem;
	}
	:global(html.tv) .pill {
		padding: 0.25rem 0.75rem;
	}
</style>
