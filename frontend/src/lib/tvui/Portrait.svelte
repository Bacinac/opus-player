<script lang="ts">
	// Every circle a person is drawn in. Nine sizes collapsed to four rungs, and
	// a rung is what the face IS on its screen, not how big somebody wanted it:
	//
	//   mark    a letter beside a name in a list
	//   beside  a face in a row you read past — the same bargain the head
	//           strikes: a face is a share of the screen
	//   face    a face you are choosing, in a shelf; the cell is the shelf's
	//           business, so this one is not a number
	//   door    the profile chooser's own face, findable from the sofa
	//
	// The picture comes in already sized — which CDN rung to ask for is the
	// site's policy and stays visible at the site. No picture means the letter,
	// on a household hue when one is given (the roster) and on the quiet ground
	// otherwise.

	let {
		src,
		instead,
		name,
		hue,
		rung
	}: {
		src?: string;
		/** what to draw when the first cannot be had. A face carried through the
		 * years needs two years to exist, and somebody photographed in one is not
		 * an error to show a broken picture for — they are a still. */
		instead?: string;
		name: string;
		/** the colour a person is told apart by across a room — COLOURS, or
		 *  whatever the roster recorded */
		hue?: string;
		rung: 'mark' | 'beside' | 'face' | 'door';
	} = $props();

	let failed = $state(false);
	const showing = $derived(failed ? instead : src);
</script>

{#if showing}
	<img
		class="portrait {rung}"
		src={showing}
		alt=""
		loading="lazy"
		decoding="async"
		onerror={() => (failed = true)}
	/>
{:else}
	<span class="portrait letter {rung}" class:hued={!!hue} style:background={hue}>
		{name.trim().slice(0, 1).toUpperCase()}
	</span>
{/if}

<style>
	.portrait {
		flex: 0 0 auto;
		display: block;
		border-radius: 50%;
		object-fit: cover;
		background: var(--surface-2);
	}
	.letter {
		display: grid;
		place-items: center;
		color: var(--muted);
		font-weight: 600;
	}
	.hued {
		color: var(--on-picture);
	}

	.mark {
		width: 2rem;
		height: 2rem;
		font-size: var(--fs-m);
	}
	.beside {
		width: clamp(2.4rem, 7.5vh, 3.4rem);
		height: clamp(2.4rem, 7.5vh, 3.4rem);
		font-size: var(--fs-2xl);
	}
	.face {
		width: 100%;
		aspect-ratio: 1;
		font-size: var(--fs-2xl);
	}
	.door {
		width: 5.5rem;
		height: 5.5rem;
		font-size: 2.1rem;
	}
	/* ten feet away a face has to be findable without leaning in */
	:global(html.tv) .door {
		width: 8.5rem;
		height: 8.5rem;
		font-size: 3.2rem;
	}
</style>
