<script lang="ts">
	// Somebody, above their work. A wall of posters answers "what else are they
	// in"; it does not answer who they are, and that is the first thing a person
	// looking at the name wants.

	import { surface } from '$lib/keep/surface.svelte';

	let {
		name,
		about,
		image,
		born,
		died,
		place
	}: {
		name: string;
		about: string;
		image: string | null;
		born?: string | null;
		died?: string | null;
		place?: string;
	} = $props();

	const years = $derived(
		[born?.slice(0, 4), died?.slice(0, 4)].filter(Boolean).join(' – ') +
			(born && !died ? ' –' : '')
	);
	const facts = $derived([years, place].filter(Boolean).join(' · '));
</script>

<section class="who" class:tv={surface.isTv}>
	{#if image}<img src={image} alt="" />{/if}
	<div class="said">
		<h2>{name}</h2>
		{#if facts}<p class="facts">{facts}</p>{/if}
		{#if about}<p class="about">{about}</p>{/if}
	</div>
</section>

<style>
	.who {
		display: flex;
		gap: 1.4rem;
		align-items: start;
		margin: 0 0 1.4rem;
	}
	img {
		flex: 0 0 auto;
		width: 7rem;
		border-radius: var(--radius-m);
		background: var(--surface);
	}
	.said {
		min-width: 0;
	}
	h2 {
		margin: 0;
		font-size: var(--fs-2xl);
		font-weight: 600;
		line-height: 1.15;
	}
	.facts {
		margin: 0.3rem 0 0;
		color: var(--muted);
		font-size: var(--fs-m);
	}
	/* a life story runs to pages; four lines of it is an introduction */
	.about {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 4;
		line-clamp: 4;
		overflow: hidden;
		margin: 0.6rem 0 0;
		max-width: 74ch;
		font-size: var(--fs-m);
		line-height: 1.45;
	}
	.tv img {
		width: 8.5rem;
	}
	.tv h2 {
		font-size: var(--fs-2xl);
	}
	.tv .about {
		font-size: var(--fs-m);
	}
</style>
