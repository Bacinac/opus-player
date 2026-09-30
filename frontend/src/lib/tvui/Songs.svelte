<script lang="ts">
	// A record's songs, the one way this surface lists them: its number, its
	// name, how long it runs, and a note in place of the number on the one that
	// is sounding.

	import { Icon } from '$lib/kit';
	import { duration, t } from '$lib/i18n';

	type Song = { id?: number; title: string; position: number; duration_s?: number | null };

	let {
		songs,
		at = -1,
		going = false,
		words,
		onpick,
		onat
	}: {
		songs: Song[];
		/** which song is on, if one of these is */
		at?: number;
		going?: boolean;
		/** the songs of these whose words can be read */
		words?: ReadonlySet<number>;
		onpick: (index: number) => void;
		/** which song the remote is standing on, for a screen that shows
		    something about it beside the list */
		onat?: (index: number) => void;
	} = $props();

	let list = $state<HTMLElement | null>(null);
	// what is playing goes to the top of the list, and what follows fills the
	// room under it
	$effect(() => {
		if (!list || at < 0) return;
		const now = list.querySelector<HTMLElement>(`[data-song="${at}"]`);
		if (!now) return;
		const by = now.getBoundingClientRect().top - list.getBoundingClientRect().top;
		list.scrollTo({ top: list.scrollTop + by, behavior: 'smooth' });
	});
</script>

<ol class="songs" bind:this={list}>
	{#each songs as song, i (i)}
		<li>
			<button
				class:on={i === at}
				data-song={i}
				onclick={() => onpick(i)}
				onfocus={() => onat?.(i)}
			>
				<span class="num">{i === at && going ? '♪' : song.position}</span>
				<span class="name">{song.title}</span>
				<span class="mark">
					{#if song.id !== undefined && words?.has(song.id)}
						<Icon name="text" size={15} />
						<span class="said">{t('sleeve.lyrics')}</span>
					{/if}
				</span>
				<span class="len">{duration(song.duration_s ?? 0)}</span>
			</button>
		</li>
	{/each}
</ol>

<style>
	.songs {
		list-style: none;
		margin: 0;
		padding: 0.6rem;
		scroll-padding-block: 0.6rem;
		overflow-y: auto;
		scrollbar-width: none;
		min-height: 0;
	}
	.songs button {
		display: grid;
		grid-template-columns: 2.2rem minmax(0, 1fr) 1.1rem auto;
		gap: 0.8rem;
		width: 100%;
		padding: 0.45rem 0.7rem;
		border: 0;
		border-radius: 10px;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
	}
	.songs .on {
		color: var(--accent);
	}
	.num,
	.len {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.num {
		text-align: right;
	}
	/* room kept whether or not this song has words, so a list does not shift
	   sideways one row at a time as the marks arrive */
	.mark {
		display: grid;
		place-items: center;
		color: var(--muted);
		opacity: 0.75;
	}
	/* the mark is a glyph on the screen and a word to anything that reads the
	   page aloud */
	.said {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
	}
	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
