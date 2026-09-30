<script lang="ts">
	import { t } from '$lib/i18n';
	import { Icon } from '$lib/kit';
	import Press from '$lib/tvui/Press.svelte';

	let { onclick }: { onclick: () => void } = $props();
</script>

<Press tone="key" label={t('info.open')} title={t('info.open')} {onclick}
	><span class="mark"><Icon name="info" size={28} /></span></Press
>

<style>
	/* no box of its own, so the mark itself is what the eye finds */
	.mark {
		display: flex;
		color: var(--accent);
	}
</style>
