<script lang="ts">
	// A picture behind words, drawn the one way this surface draws one.
	//
	// Two places need it and they are the same picture: the frame lays it behind
	// a shelf, and the screen about one thing lays it behind that. They were one
	// component with the other half copied, which is how two crops of one film
	// end up with two different veils over them.

	import { cssUrl } from '$lib/kit';

	let { art, wash = false }: { art: string; wash?: boolean } = $props();
</script>

{#key art}
	<div class="fanart" class:wash style:background-image={cssUrl(art)}></div>
{/key}
<div class="veil"></div>

<style>
	.fanart {
		position: absolute;
		inset: 0;
		background-size: cover;
		background-position: center 28%;
		animation: rise 0.5s ease both;
	}
	/* a poster is the wrong shape to look at sideways: thrown far out of focus it
	   stops being a picture and becomes the colour of one */
	.fanart.wash {
		filter: blur(50px) saturate(130%);
		transform: scale(1.3);
	}
	@keyframes rise {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
	/* Never fully drawn and never fully gone. Sideways it closes over the words;
	   downwards it closes over the shelves, because a poster on a bright picture
	   is a poster nobody can pick out — which is what the skin's own floor fade
	   is for. What is left is the top corner, where the picture is worth seeing
	   and nothing is written. */
	.veil {
		position: absolute;
		inset: 0;
		background:
			linear-gradient(
				to right,
				var(--bg) 0%,
				color-mix(in srgb, var(--bg) 86%, transparent) 28%,
				color-mix(in srgb, var(--bg) 48%, transparent) 58%,
				color-mix(in srgb, var(--bg) 28%, transparent) 82%,
				color-mix(in srgb, var(--bg) 62%, transparent) 100%
			),
			linear-gradient(
				to bottom,
				transparent 0%,
				color-mix(in srgb, var(--bg) 45%, transparent) 38%,
				color-mix(in srgb, var(--bg) 84%, transparent) 66%,
				color-mix(in srgb, var(--bg) 96%, transparent) 100%
			);
	}
</style>
