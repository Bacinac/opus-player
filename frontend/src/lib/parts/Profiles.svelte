<script lang="ts">
	// Who is watching. Shown once past the door, because the door is the house
	// and this is the person — two different questions, and only the first one
	// has a password.
	//
	// Built for the hardest input in the house: four arrow keys and OK. Big
	// targets, one row, nothing to type: nobody is made here, everybody on it
	// has an account in the library.

	import { t } from '#lib/i18n/index.js';
	import { surface } from '#lib/keep/surface.svelte.js';
	import { focusFirst } from '#lib/tv/spatial.svelte.js';
	import type { Profile } from '#lib/keep/types.js';
	import Portrait from '#lib/tvui/Portrait.svelte';
	import { request } from '#lib/kit/index.js';
	import { cropOf } from '#lib/opus/index.js';

	let { onpicked }: { onpicked: () => void } = $props();

	let people = $state<Profile[]>([]);
	let loading = $state(true);
	let problem = $state('');

	async function load() {
		problem = '';
		const said = await request<Profile[]>('/api/users', {}, { failed: (detail) => (problem = detail) });
		people = said ?? [];
		// a question with one answer is not asked: a guest, and a guest's box,
		// can only ever be their own person
		if (people.length === 1 && (await pick(people[0].key))) return;
		loading = false;
		// every other screen that arrives on a television puts the remote on
		// something. This one did not, and a screen where nothing holds the
		// remote is a screen where OK does nothing at all — which is indis-
		// tinguishable from a profile that cannot be chosen.
		if (surface.isTv) setTimeout(() => focusFirst('.pick .faces button'), 0);
	}

	async function pick(key: string): Promise<boolean> {
		const picked = await request(`/api/users/${encodeURIComponent(key)}/pick`, { method: 'POST' });
		if (picked) onpicked();
		return Boolean(picked);
	}

	$effect(() => {
		load();
	});
</script>

<div class="pick" class:tv={surface.isTv}>
	<h1>{t('profiles.who')}</h1>

	{#if loading}
		<p class="muted">{t('common.loading')}</p>
	{:else}
		<div class="faces">
			{#each people as who (who.key)}
				<button class="face" data-own-mark onclick={() => pick(who.key)}>
					<Portrait
						rung="door"
						src={who.face ? cropOf(who.face) : undefined}
						hue={who.colour || undefined}
						name={who.name}
					/>
					<span class="name">{who.name}</span>
				</button>
			{/each}
		</div>

		{#if !people.length && !problem}<p class="muted">{t('profiles.none')}</p>{/if}
		{#if problem}<p class="problem">{problem}</p>{/if}
	{/if}
</div>

<style>
	.pick {
		/* the whole screen, not most of it. Centring inside 70vh puts a door
		   screen in the upper two thirds, which on a desk is a considered
		   margin and across a room is simply not centred. */
		min-height: 100vh;
		display: grid;
		align-content: center;
		justify-items: center;
		gap: 1.6rem;
		padding: 2rem 1rem;
	}
	h1 {
		margin: 0;
		font-weight: 500;
	}
	.faces {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 1.6rem;
	}
	.face {
		display: grid;
		justify-items: center;
		gap: 0.6rem;
		padding: 0.4rem;
		border: none;
		background: transparent;
		color: inherit;
		font: inherit;
		cursor: pointer;
		border-radius: var(--radius-m);
	}
	.face :global(.portrait) {
		border: 3px solid transparent;
		transition: border-color 0.12s ease;
	}
	.face:hover :global(.portrait),
	.face:focus-visible :global(.portrait),
	.tv .face:focus :global(.portrait) {
		border-color: var(--accent);
	}
	.tv .face {
		transition: transform 140ms ease;
	}
	.tv .face:focus {
		transform: scale(1.08);
		z-index: 2;
	}
	.tv .face:focus .name {
		color: var(--accent);
	}
	.tv .faces {
		gap: 2.6rem;
	}
	.problem {
		color: var(--danger);
	}
</style>
