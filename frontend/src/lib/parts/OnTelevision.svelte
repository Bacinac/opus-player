<script lang="ts">
	// The bar for a film this screen is not playing but a television is: the
	// film's own keys, reaching over there, on every page until it ends. A
	// photograph shown over there has one key, the one that puts it away.

	import { art } from '$lib/ask/art';
	import { formatDate, t } from '$lib/i18n';
	import { tileOf } from '$lib/opus';
	import PlayerBar from '$lib/parts/PlayerBar.svelte';
	import { tvFilm } from '$lib/keep/tvFilm.svelte';
	import { tvPhoto } from '$lib/keep/tvPhoto.svelte';
</script>

{#if tvFilm.on}
	{@const on = tvFilm.on}
	<div class="stays" data-stays>
		<PlayerBar
			art={art(on.cover, 92)}
			title={on.title}
			subtitle={[t('cast.showing', { name: on.box.name }), on.subtitle].filter(Boolean).join(' · ')}
			position={tvFilm.position}
			total={tvFilm.duration}
			going={tvFilm.playing}
			toggle={() => tvFilm.toggle()}
			seek={(to) => tvFilm.seek(to)}
			seekable={tvFilm.started}
			onclose={() => void tvFilm.stop()}
		/>
	</div>
{:else if tvPhoto.on && tvPhoto.photo}
	{@const photo = tvPhoto.photo}
	<div class="stays" data-stays>
		<PlayerBar
			art={tileOf(photo.id, photo.turn)}
			title={photo.taken_at ? formatDate(photo.taken_at) : t('photos.photo')}
			subtitle={t('cast.showing', { name: tvPhoto.on.name })}
			onclose={() => void tvPhoto.stop()}
		/>
	</div>
{/if}

<style>
	/* the bar is fixed, so this wrapper is only a handle for the arrows to find
	   it by from whatever is standing over the screen */
	.stays {
		display: contents;
	}
</style>
