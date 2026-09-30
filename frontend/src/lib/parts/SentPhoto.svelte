<script lang="ts">
	// The photograph a phone is showing on this television, or the photographs
	// the house asked for one after another, over whatever the television was
	// doing, until they are put away, back does, or they are left there long
	// enough to have been forgotten.

	import { placeholderOf } from '$lib/opus';
	import PhotoViewer from '$lib/opus/PhotoViewer.svelte';
	import { t } from '$lib/i18n';
	import { recordingOf } from '$lib/ask/ability';
	import { onBack } from '$lib/keep/back.svelte';
	import { shown } from '$lib/keep/tvPhoto.svelte';

	// registered when a picture arrives, so it stands in front of every step the
	// page under it already had
	$effect(() => {
		if (shown.photo || shown.slides)
			return onBack(
				() => {
					shown.close();
					return true;
				},
				() => true
			);
	});
</script>

{#if shown.photo}
	<PhotoViewer
		photo={shown.photo}
		placeholder={placeholderOf(shown.photo.hash)}
		plays={recordingOf}
		onclose={() => shown.close()}
	/>
{:else if shown.slides}
	<!-- never focused: the remote's keys stay with this page, whose back puts it away -->
	<iframe class="slides" src={shown.slides} title={t('nav.photos')} tabindex="-1"></iframe>
{/if}

<style>
	.slides {
		position: fixed;
		inset: 0;
		width: 100%;
		height: 100%;
		border: 0;
		z-index: 40;
		pointer-events: none;
		background: var(--picture-ground);
	}
</style>
