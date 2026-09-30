<script lang="ts">
	// Who is watching. Shown once past the door, because the door is the house
	// and this is the person — two different questions, and only the first one
	// has a password.
	//
	// Built for the hardest input in the house: four arrow keys and OK. Big
	// targets, one row, nothing to type.

	import { t } from '$lib/i18n';
	import { surface } from '$lib/keep/surface.svelte';
	import { focusFirst } from '$lib/tv/spatial.svelte';
	import type { Profile } from '$lib/keep/types';
	import { COLOURS } from '$lib/tvui/colours';
	import Portrait from '$lib/tvui/Portrait.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import { json, request } from '$lib/kit';
	import { me } from '$lib/opus';

	let { onpicked }: { onpicked: () => void } = $props();

	let people = $state<Profile[]>([]);
	let loading = $state(true);
	let adding = $state(false);
	let name = $state('');
	let problem = $state('');


	async function load() {
		problem = '';
		const said = await request<Profile[]>('/api/users', {}, { failed: (detail) => (problem = detail) });
		people = said ?? [];
		loading = false;
		// nobody at all, not even on the roster: the first screen is the one that
		// makes somebody, not one that asks you to choose from nothing
		adding = said !== null && people.length === 0;
		// every other screen that arrives on a television puts the remote on
		// something. This one did not, and a screen where nothing holds the
		// remote is a screen where OK does nothing at all — which is indis-
		// tinguishable from a profile that cannot be chosen.
		if (surface.isTv) setTimeout(() => focusFirst('.pick .faces button'), 0);
	}

	async function pick(key: string) {
		const picked = await request(`/api/users/${encodeURIComponent(key)}/pick`, { method: 'POST' });
		if (picked) onpicked();
	}

	async function add(event: Event) {
		event.preventDefault();
		problem = '';
		const made = await request<Profile>(
			'/api/users',
			json({ name, colour: COLOURS[people.length % COLOURS.length] }),
			{ failed: (detail) => (problem = detail) }
		);
		if (!made) return;
		name = '';
		adding = false;
		await load();
		if (people.length === 1) pick(made.key);
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
					<Portrait rung="door" hue={who.colour || undefined} name={who.name} />
					<span class="name">{who.name}</span>
				</button>
			{/each}

			{#if !adding && !me.guest}
				<button class="face add" data-own-mark onclick={() => (adding = true)}>
					<Portrait rung="door" name="+" />
					<span class="name">{t('profiles.add')}</span>
				</button>
			{/if}
		</div>

		{#if adding}
			<form onsubmit={add}>
				<!-- svelte-ignore a11y_autofocus -->
				<input bind:value={name} placeholder={t('profiles.name')} autofocus required />
				<Press tone="go" type="submit">{t('profiles.add')}</Press>
				{#if people.length}
					<Press tone="bare" onclick={() => (adding = false)}>{t('common.close')}</Press>
				{/if}
			</form>
		{/if}
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
	.add :global(.portrait) {
		background: transparent;
		border: 2px dashed var(--border);
		color: var(--muted);
	}
	.face:hover :global(.portrait),
	.face:focus-visible :global(.portrait) {
		border-color: var(--accent);
	}
	.tv .face {
		transition: transform 140ms ease;
	}
	.tv .face:focus-visible {
		transform: scale(1.08);
		z-index: 2;
	}
	.tv .face:focus-visible .name {
		color: var(--accent);
	}
	.tv .faces {
		gap: 2.6rem;
	}
	form {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	input {
		padding: 0.5rem 0.7rem;
		border-radius: var(--radius-s);
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
		font: inherit;
	}
	.problem {
		color: var(--danger);
	}
</style>
