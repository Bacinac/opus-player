<script lang="ts">
	// Who an artist plays with: the band a singer is in, the people a band is
	// made of. A name here is somewhere to go and not a word, so pressing one
	// stands this screen on that artist.

	import type { Card } from '$lib/keep/types';
	import Press from '$lib/tvui/Press.svelte';

	let {
		label,
		who,
		onopen
	}: {
		label: string;
		who: { id: number; name: string }[];
		onopen?: (c: Card) => void;
	} = $props();
</script>

{#if who.length}
	<p class="by">
		<span class="label">{label}</span>
		<span class="names">
			{#each who as person, i (person.id)}
				<!-- the dot goes INSIDE the name it follows: as an element of its own
				     it wrapped to the head of the next line and stood there in front
				     of a name, separating it from nothing -->
				<span class="one" class:after={i < who.length - 1}><Press
						tone="bare"
						onclick={() =>
							onopen?.({
								kind: 'artist',
								id: person.id,
								title: person.name,
								image: null,
								backdrop: null,
								state: null,
								overview: '',
								round: true,
								// neither played nor asked for, same as any artist card
								person: true
							})}>{person.name}</Press></span>
			{/each}
		</span>
	</p>
{/if}

<style>
	/* The label keeps its own column so the names have one too: a second line of
	   a long band begins under the first NAME rather than under the word in
	   front of it. */
	.by {
		margin: 0.15rem 0 0;
		font-size: var(--fs-m);
		display: flex;
		align-items: baseline;
		gap: 0.55rem;
	}
	.names {
		min-width: 0;
	}
	.label {
		flex: none;
		color: var(--muted);
		font-size: var(--fs-xs);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.label::after {
		content: ':';
	}
	/* one name and the dot after it are one unbreakable thing, so a line never
	   begins with a separator standing in front of a name */
	.one {
		white-space: nowrap;
	}
	.one.after::after {
		content: '·';
		margin: 0 0.35rem;
		color: var(--muted);
	}
</style>
