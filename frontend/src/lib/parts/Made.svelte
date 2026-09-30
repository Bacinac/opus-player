<script lang="ts">
	// Who made it, with each name a way into the rest of their work. Said under
	// the facts on a film's screen and on a series', which is why it is said in
	// neither of them.

	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { t } from '$lib/i18n';
	import type { Named } from '$lib/keep/types';
	import Press from '$lib/tvui/Press.svelte';
	import { sectionOf } from '$lib/say/ways';

	/** `said` false where the page names the row itself, beside it */
	let { people, said = true }: { people: Named[]; said?: boolean } = $props();
</script>

{#if people.length}
	<p class="by">
		{#if said}<span>{people.length > 1 ? t('play.directors') : t('play.director')}</span>{/if}
		{#each people as who, i (who.name)}
			{#if i > 0},{' '}{/if}
			{#if who.id}
				<Press tone="bare" onclick={() => goto(`${sectionOf(page.url.pathname)}?person=${who.id}`)}>
					<span class="named">{who.name}</span>
				</Press>
			{:else}{who.name}{/if}
		{/each}
	</p>
{/if}

<style>
	.by {
		margin: 0.5rem 0 0;
		font-size: var(--fs-m);
	}
	.by span {
		color: var(--muted);
	}
	.named {
		color: var(--text);
		text-decoration: underline;
		text-decoration-color: color-mix(in srgb, var(--text) 35%, transparent);
		text-underline-offset: 3px;
	}
</style>
