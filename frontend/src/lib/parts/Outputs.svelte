<script lang="ts">
	import Choose from '$lib/tvui/Choose.svelte';
	import Press from '$lib/tvui/Press.svelte';
	import { Icon, Tag } from '$lib/kit';
	// Where the sound comes out, and how loud — the same control wherever the
	// record is shown, because a person who has moved from the bar to the full
	// screen has not changed their mind about what a speaker button looks like.

	import { formatNumber, t } from '$lib/i18n';
	import { cast } from '$lib/keep/cast.svelte';
	import { surface } from '$lib/keep/surface.svelte';

	let picking = $state(false);

	/** What the button says, which is always where the sound is coming out. The
	 *  speaker glyph said only that a speaker exists; the name says which one,
	 *  and a name is something to press. */
	const outName = $derived(
		cast.outputs.find((o) => o.id === cast.active)?.name ||
			(surface.isTv ? t('cast.thisTv') : t('cast.browser'))
	);

	// On the television, the screen itself IS the multichannel output: offering
	// both "this device" and "OPUS TV" offered the same thing twice. What is
	// worth choosing there is the other road — the DAC.
	const elsewhere = $derived(
		cast.outputs.filter(
			(o) => o.id !== 'browser' && !(surface.isTv && o.id === 'multi' && o.entity === 'tv')
		)
	);

	function pick(choice: typeof cast.choice) {
		picking = false;
		void cast.choose(choice);
	}
</script>

{#if cast.remote}
	<Tag tone="busy">{t('cast.remote')}</Tag>
{/if}
{#if cast.casting}
	<Press tone="key" onclick={() => cast.setVolume('down')} label={t('cast.volumeDown')}><Icon name="minus" size={16} /></Press>
	<Press tone="key" onclick={() => cast.setVolume('up')} label={t('cast.volumeUp')}><Icon name="plus" size={16} /></Press>
	{#if cast.volume != null}
		<span class="vol" class:muted-out={cast.mute}>{formatNumber(cast.volume)}</span>
	{/if}
{/if}

<div class="out">
	<Press
		tone="pill"
		on={cast.casting}
		onclick={() => (picking = !picking)}
		title={cast.casting ? t('cast.on', { name: outName }) : t('cast.output')}
	>
		{outName}
	</Press>
	{#if picking}
		<Choose
			over
			options={[
				{ key: 'auto', label: t('cast.auto') },
				{ key: 'browser', label: surface.isTv ? t('cast.thisTv') : t('cast.browser') },
				...elsewhere.map((o) => ({ key: o.id, label: o.name ?? o.id }))
			]}
			chosen={[cast.choice]}
			onpick={(key) => pick(key as typeof cast.choice)}
			onclose={() => (picking = false)}
		/>
	{/if}
</div>

<style>
	.vol {
		font-variant-numeric: tabular-nums;
		font-size: 0.8em;
		color: var(--muted);
	}
	.vol.muted-out {
		text-decoration: line-through;
	}
	.out {
		position: relative;
	}
	/* the chooser flows where the button is; the sound menu stands over the
	   corner the button lives in */
	.out :global(.held) {
		position: absolute;
		right: 0;
		bottom: 2.6rem;
		z-index: 20;
		/* as wide as the longest name in it: the chooser clips what does not fit
		   with an ellipsis, and a list of devices whose names are cut off is a
		   list you cannot choose from */
		min-width: max-content;
		max-width: 20rem;
	}
</style>
