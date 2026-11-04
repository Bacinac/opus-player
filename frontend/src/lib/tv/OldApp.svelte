<script lang="ts">
	// Only an app that has no update() of its own: from v1.0.64 the box offers a
	// newer one on every return and Settings updates it on a press. Before that it
	// offered at most every six hours, and the step that stops a person is
	// Android's own "not allowed from this source", which nothing here can press.
	import { Dialog, request } from '#lib/kit/index.js';
	import { t } from '#lib/i18n/index.js';
	import Held from '#lib/tvui/Held.svelte';
	import Press from '#lib/tvui/Press.svelte';
	import { onBox } from './bridge';
	import { focusContent } from './spatial.svelte';

	const build = onBox((box) => (typeof box.update === 'function' ? 0 : (box.version?.() ?? 0))) ?? 0;
	let offered = $state('');

	function close() {
		offered = '';
		setTimeout(focusContent, 0);
	}

	$effect(() => {
		if (!build) return;
		void (async () => {
			const shelf = await request<{ versionCode: number; versionName: string }>(
				'/api/app/apk.json',
				{},
				{ on: { 404: () => {} } }
			);
			if (shelf && shelf.versionCode > build) offered = shelf.versionName;
		})();
	});
</script>

{#if offered}
	<Dialog title={t('oldApp.title')} size="narrow" onclose={close}>
		<Held onclose={close} still={false} first=".old-app button">
			<div class="old-app">
				<p>{t('oldApp.offered', { version: offered })}</p>
				<ol>
					<li>{t('oldApp.install')}</li>
					<li>{t('oldApp.allow')}</li>
					<li>{t('oldApp.back')}</li>
				</ol>
				<Press onclick={close}>{t('common.ok')}</Press>
			</div>
		</Held>
	</Dialog>
{/if}

<style>
	.old-app {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.8rem;
	}
	.old-app p,
	.old-app ol {
		margin: 0;
	}
	.old-app ol {
		padding-left: 1.4rem;
		display: grid;
		gap: 0.5rem;
	}
</style>
