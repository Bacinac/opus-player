<script lang="ts">
	// The key in a photograph's viewer that shows it on a television, and from
	// then on every photograph this phone moves to, until it is pressed again.

	import { untrack } from 'svelte';
	import { Button } from '$lib/kit';
	import { t } from '$lib/i18n';
	import Choose from '$lib/tvui/Choose.svelte';
	import { televisions, type Box } from '$lib/keep/tvFilm.svelte';
	import { tvPhoto, type Photo } from '$lib/keep/tvPhoto.svelte';

	let { photo }: { photo: Photo } = $props();

	let boxes = $state<Box[]>([]);
	let choosing = $state(false);
	void televisions().then((got) => (boxes = got));

	$effect(() => {
		const now = photo;
		if (tvPhoto.on) untrack(() => tvPhoto.show(now));
	});

	function toTv() {
		if (boxes.length === 1) tvPhoto.start(boxes[0]);
		else choosing = true;
	}
</script>

{#if tvPhoto.on}
	<Button selected onclick={() => void tvPhoto.stop()}>{t('cast.showing', { name: tvPhoto.on.name })}</Button>
{:else if boxes.length}
	<Button onclick={toTv}>{t('cast.toTv')}</Button>
{/if}

{#if choosing}
	<Choose
		over
		options={boxes.map((box) => ({ key: String(box.id), label: box.name }))}
		onpick={(key) => {
			choosing = false;
			const box = boxes.find((b) => String(b.id) === key);
			if (box) tvPhoto.start(box);
		}}
		onclose={() => (choosing = false)}
	/>
{/if}
