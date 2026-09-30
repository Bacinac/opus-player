<script lang="ts">
	// The page's own ground on a television: the fanart of whatever has the
	// remote, whole, behind everything, under a veil that lets it through where
	// there is nothing to read and closes over it where the shelves stand.
	//
	// It belongs to the frame rather than to the panel that describes the thing.
	// Inside the panel it would be inside the scrolling column, and anything the
	// frame did to that column — stepping it back while the menu is being used —
	// would be done to the picture as well.

	import { page } from '$app/state';
	import { hero } from '$lib/keep/hero.svelte';
	import { preview } from '$lib/keep/preview.svelte';
	import { ground } from '$lib/ask/art';
	import Fanart from '$lib/tv/Fanart.svelte';

	// Walking the menu, the ground is the SECTION'S — the shelf you are asking
	// about, not the last poster the remote happened to touch on the one before.
	// And arriving cold, it is the section you arrived AT: the photographs have
	// no cards for the remote to land on, so without this third answer that
	// page stood in front of nothing while every other one had its picture.
	const here = $derived(page.url.pathname.split('/').filter(Boolean)[0] ?? 'home');
	const card = $derived(
		(preview.section && preview.fronts[preview.section]) ||
			hero.behind ||
			preview.fronts[here] ||
			null
	);
	// and only while browsing: once a thing is opened, the screen about it draws
	// its own picture, and two crops of one picture is the seam this avoids
	const art = $derived(hero.open ? null : ground(card));
</script>

{#if art}
	<div class="ground" aria-hidden="true">
		<Fanart {art} wash={!card?.backdrop} />
	</div>
{/if}

<style>
	.ground {
		position: fixed;
		inset: 0;
		z-index: -1;
		pointer-events: none;
	}
</style>
