<script lang="ts">
	// A record ten feet away: the sleeve standing on the left, its songs down the
	// right. The same whether the record is playing or has only been opened, so
	// putting it on does not change what the screen is.

	import type { Snippet } from 'svelte';
	import { art } from '$lib/ask/art';
	import Songs from './Songs.svelte';

	type Song = { id?: number; title: string; position: number; duration_s?: number | null };

	let {
		cover = null,
		title,
		by = '',
		quiet = '',
		songs,
		at = -1,
		going = false,
		words,
		onpick,
		onat,
		keys,
		tabs,
		instead
	}: {
		cover?: string | null;
		title: string;
		by?: string;
		quiet?: string;
		songs: Song[];
		/** which song is on, if one of these is */
		at?: number;
		going?: boolean;
		/** the songs of these whose words can be read */
		words?: ReadonlySet<number>;
		onpick: (index: number) => void;
		/** which song the remote is standing on */
		onat?: (index: number) => void;
		/** what may be done about the whole record, under its name */
		keys?: Snippet;
		/** a choice above the songs of what the right-hand side shows */
		tabs?: Snippet;
		/** shown in place of the songs when the choice is something else */
		instead?: Snippet;
	} = $props();

</script>

<div class="turntable">
	<section class="record">
		{#if cover}<img class="cover" src={art(cover, 700)} alt="" />{/if}
		<h1>{title}</h1>
		{#if by}<p class="by">{by}</p>{/if}
		{#if quiet}<p class="quiet">{quiet}</p>{/if}
		{#if keys}<div class="keys">{@render keys()}</div>{/if}
	</section>
	<section class="side">
		{#if tabs}<div class="tabs" role="group">{@render tabs()}</div>{/if}
		{#if instead}
			{@render instead()}
		{:else}
			<Songs {songs} {at} {going} {words} {onpick} {onat} />
		{/if}
	</section>
</div>

<style>
	/* the record's column is as wide as its height allows: cover, two lines of
	   title, artist and a line more above the bar on a 540-high page */
	.turntable {
		display: grid;
		grid-template-columns: minmax(0, 16rem) minmax(0, 38rem);
		grid-template-rows: minmax(0, 1fr);
		column-gap: 3rem;
		min-height: 0;
	}
	.record {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-height: 0;
	}
	.cover {
		width: 100%;
		min-height: 0;
		flex: 0 1 auto;
		aspect-ratio: 1;
		object-fit: cover;
		border-radius: 12px;
		box-shadow: var(--shadow-xl);
	}
	h1 {
		margin: 0.6rem 0 0;
		font-size: var(--fs-2xl);
		line-height: 1.15;
	}
	p {
		margin: 0;
	}
	.by {
		font-size: var(--fs-xl);
	}
	.quiet {
		color: var(--muted);
	}
	.keys {
		display: flex;
		gap: 0.6rem;
		margin-top: 0.4rem;
	}
	.side {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 1rem;
		min-height: 0;
	}
	.side:not(:has(.tabs)) {
		grid-template-rows: minmax(0, 1fr);
	}
	.tabs {
		display: flex;
		gap: 0.4rem;
	}
</style>
