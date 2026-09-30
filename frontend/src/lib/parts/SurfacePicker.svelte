<script lang="ts">
	// A development instrument, not a feature. Detection is the answer — this
	// only exists so all four surfaces can be looked at from one machine while
	// they are being shaped, and it is compiled out of the shipped build.
	//
	// The real override survives it: `?surface=tv` in the address, for the one
	// case detection cannot see, which is a laptop plugged into a television.

	import { surface, SURFACES, type Surface } from '$lib/keep/surface.svelte';
	import { t, type MessageKey } from '$lib/i18n';
	import Choose from '$lib/tvui/Choose.svelte';
</script>

<div class="picker" data-aside>
	<span class="label">{t('surface.label')}</span>
	<Choose
		as="row"
		options={[
			{ key: 'auto', label: t('surface.auto') },
			...SURFACES.map((s) => ({ key: s, label: t(`surface.${s}` as MessageKey) }))
		]}
		chosen={[surface.forced ?? 'auto']}
		onpick={(key) => surface.force(key === 'auto' ? null : (key as Surface))}
	/>
</div>

<style>
	.picker {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		flex-wrap: wrap;
		margin-bottom: 1.25rem;
		padding-bottom: 1rem;
		border-bottom: 1px solid var(--border);
	}
	.label {
		color: var(--muted);
		font-size: var(--fs-s);
		margin-right: 0.3rem;
	}
</style>
