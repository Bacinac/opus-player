<script lang="ts" module>
	export type Wired = {
		id: number;
		name: string;
		source: string;
		/** what the box was plugged into when its input was chosen */
		wired_on: string;
		/** what it says it is plugged into now */
		sink: string;
	};
</script>

<script lang="ts">
	// Which of the receiver's inputs each television arrives on. The input is the
	// box's and not the install's: turning the receiver to the Shield while the
	// terrace's box plays a film sends that film nowhere.

	import { t } from '$lib/i18n';
	import Choose from '$lib/tvui/Choose.svelte';
	import Rows from '$lib/tvui/Rows.svelte';
	import { json, request } from '$lib/kit';

	let {
		sources,
		boxes,
		onchanged
	}: { sources: string[]; boxes: Wired[]; onchanged: () => void } = $props();

	const inputs = (box: Wired) => [
		{ key: '', label: t('settings.noReceiver') },
		...[...new Set([...sources, ...(box.source ? [box.source] : [])])].map((s) => ({
			key: s,
			label: s
		}))
	];

	async function wire(box: Wired, source: string) {
		if (await request(`/api/cast/boxes/${box.id}`, json({ source }, 'PUT'))) onchanged();
	}
</script>

<Rows>
	{#each boxes as box (box.id)}
		<div class="row">
			<span class="what"
				>{box.name}{#if box.sink && box.wired_on && box.sink !== box.wired_on}<em
						>{t('settings.pluggedElsewhere', { sink: box.sink })}</em
					>{:else if box.sink}<em>{t('settings.pluggedInto', { sink: box.sink })}</em>{/if}</span
			>
			<Choose
				said=""
				chosen={[box.source]}
				options={inputs(box)}
				onpick={(source) => wire(box, source)}
			/>
		</div>
	{/each}
</Rows>
