<script lang="ts">
	// The top of a whole shelf on a television: what it is and how many, and how
	// it is arranged. The arrangement sits beside the wall it rearranges, not in a
	// menu: nobody finds a menu inside a menu from a sofa.

	import { t } from '$lib/i18n';
	import { ORDERS, natural, shelf, type Order } from '$lib/keep/shelf.svelte';
	import Press from '$lib/tvui/Press.svelte';

	let { section }: { section: string } = $props();

	const chosen = $derived(shelf.of(section));
</script>

<header class="wall-head">
	<h1>{t(`wall.${section}` as never)}</h1>
	<div class="orders" role="group" aria-label={t('arrange.label')}>
		<span class="label">{t('arrange.label')}</span>
		{#each ORDERS as order (order)}
			<Press
				tone="pill"
				on={chosen.order === order}
				onclick={() => shelf.choose(section, order as Order)}
			>
				{t(`shelf.${order}.${chosen.order === order ? chosen.way : natural(order)}` as never)}
			</Press>
		{/each}
	</div>
</header>

<style>
	.wall-head {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.8rem;
	}
	h1 {
		margin: 0;
		font-size: var(--fs-2xl);
		line-height: 1.1;
	}
	.orders {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}
	.label {
		margin-right: 0.3rem;
		color: var(--muted);
	}
</style>
