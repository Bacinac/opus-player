<script lang="ts">
	// The last rung: nothing left to close, and the only things back can still
	// mean.
	import { goto } from '$app/navigation';
	import { Dialog } from '$lib/kit';
	import { t } from '$lib/i18n';
	import { watching } from '$lib/keep/watching.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import { onBox } from './bridge';
	import { rung } from './rung.svelte';
	import { focusFirst } from './spatial.svelte';

	// Where the home key leads here, leaving is not a thing that can happen: the
	// app closes and the system asks for a home screen, which is this one.
	// Something to quit TO. Only the wrapper can leave an app, and only when it
	// is not itself the launcher — a browser tab has neither, so the offer was
	// a button that did nothing wherever most people press it.
	const canQuit = typeof window.opusTv?.quit === 'function';

	$effect(() => {
		queueMicrotask(() => focusFirst('.ways button'));
	});

	/** Every way out of the panel takes the panel with it.
	 *
	 * Only Cancel used to. Settings opened underneath and the panel stayed on
	 * top of it holding the ring, so the answer to "what now?" was still being
	 * asked after it had been answered. */
	function went(go: () => void) {
		rung.leaving = false;
		go();
	}
</script>

<Dialog title={t('leave.what')} size="narrow" onclose={() => (rung.leaving = false)}>
	<div class="ways" data-holds-remote>
		<Press onclick={() => (rung.leaving = false)}>{t('common.cancel')}</Press>
		<Press onclick={() => went(() => goto('/settings'))}>{t('leave.settings')}</Press>
		<Press onclick={() => went(() => watching.again())}>{t('profiles.switch')}</Press>
		{#if canQuit}
			<Press onclick={() => onBox((box) => box.quit?.())}>{t('leave.quit')}</Press>
		{/if}
	</div>
</Dialog>

<style>
	.ways {
		display: flex;
		flex-wrap: wrap;
		gap: 0.8rem;
		justify-content: center;
	}
</style>
