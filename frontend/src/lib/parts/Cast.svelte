<script lang="ts">
	// Who is in it, with faces, and each of them a way into the rest of their
	// work. A film's screen and a series' show the same row.

	import { art } from '$lib/ask/art';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import type { Person } from '$lib/keep/types';
	import Portrait from '$lib/tvui/Portrait.svelte';
	import { sectionOf } from '$lib/say/ways';
	import { sideways } from '$lib/tvui/sideways';

	let { people }: { people: Person[] } = $props();
</script>

{#if people.length}
	<ul class="cast" use:sideways>
		{#each people.slice(0, 7) as person (person.id)}
			<li>
				<button onclick={() => goto(`${sectionOf(page.url.pathname)}?person=${person.id}`)}>
					<Portrait
						rung="beside"
						src={person.profile_url ? art(person.profile_url, 154) : undefined}
						name={person.name}
					/>
					<span class="who">
						<strong>{person.name}</strong>
						{#if person.character}<em>{person.character}</em>{/if}
					</span>
				</button>
			</li>
		{/each}
	</ul>
{/if}

<style>
	/* One row, and everybody in it at the same size. Squeezed into equal columns
	   the whole billing fitted and no name did — "Angelina J…", "Vincent Lin…" —
	   which is a row of faces nobody can read. They keep their width and the row
	   is walked sideways. */
	.cast {
		display: flex;
		flex-wrap: nowrap;
		gap: 0.9rem;
		margin: 0;
		padding: 0;
		list-style: none;
		overflow-x: auto;
		scrollbar-width: none;
	}
	.cast::-webkit-scrollbar {
		display: none;
	}
	li {
		flex: none;
		width: 7.5rem;
		min-width: 0;
	}
	button {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.35rem;
		width: 100%;
		min-width: 0;
		padding: 0.3rem 0.2rem;
		border: none;
		border-radius: var(--radius-m);
		background: none;
		color: inherit;
		font: inherit;
		font-size: var(--fs-s);
		text-align: center;
		cursor: pointer;
	}
	button:focus-visible {
		outline: none;
		background: color-mix(in srgb, var(--accent) 22%, transparent);
	}
	.who {
		min-width: 0;
		max-width: 100%;
	}
	strong {
		display: block;
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	em {
		display: block;
		font-style: normal;
		color: var(--muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
