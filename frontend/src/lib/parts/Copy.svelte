<script lang="ts">
	// The row of facts about the copy on the disk, and who made it. The same row
	// on a film's screen and on a series', which is why it is not written on
	// either of them.

	import { goto } from '$app/navigation';
	import { Icon, Tag } from '$lib/kit';
	import type { Chip } from '$lib/say/copy';
	import Press from '$lib/tvui/Press.svelte';
	import { sideways } from '$lib/tvui/sideways';

	let { chips }: { chips: Chip[] } = $props();
</script>

{#if chips.length}
	<ul class="copy" use:sideways>
		{#each chips as chip (chip.icon + chip.label)}
			<li>
				{#snippet mark()}
					<!-- Every fact in this row wears the same pill: the mark a format is
					     known by, or an icon and the name of a thing that has no mark.
					     A studio is a NAME here. Its own mark comes off the catalogue as
					     artwork drawn for a title card — a filled block with the letters
					     knocked out of it — and seventeen pixels tall, flattened to one
					     colour so it survives either theme, three of those in a row are
					     three white smudges. Read from a sofa a word beats a mark that
					     cannot be read at all. -->
					<Tag tone="quiet">
						{#if chip.flag}
							<img class="mark" src={chip.flag} alt={chip.label} />
						{:else}
							<Icon name={chip.icon} />
						{/if}
						<!-- a mark that says the whole fact leaves nothing to write after
						     it; a mark for the format still needs whose voice it is -->
						{#if chip.label}{chip.label}{/if}
					</Tag>
				{/snippet}
				{#if chip.to}
					<Press tone="bare" onclick={() => goto(chip.to!)}>{@render mark()}</Press>
				{:else}
					{@render mark()}
				{/if}
			</li>
		{/each}
	</ul>
{/if}

<style>
	/* the same bargain: what a copy is made of is a row of facts read at a
	   glance, not a row of headings */
	/* One row. A second line of facts pushes the faces under it off the bottom of
	   the screen, and the screen about a film is a card that has to fit — so what
	   does not fit is reached sideways instead. */
	.copy {
		--tag-font: var(--fs-m);
		display: flex;
		flex-wrap: nowrap;
		align-items: center;
		gap: 0.4rem;
		margin: 0;
		padding: 0;
		list-style: none;
		overflow-x: auto;
		scrollbar-width: none;
	}
	.copy::-webkit-scrollbar {
		display: none;
	}
	.copy > li {
		flex: none;
	}
	/* Our own marks, drawn for this: white artwork with its own inner detail,
	   which is what the dark theme wants. On a light ground they are turned over
	   rather than filled in, so a mark keeps the shape it was drawn with in both
	   themes. One height for all of them — a mark is a word here, and words in a
	   row are the same size. */
	.mark {
		display: block;
		height: 1rem;
		max-width: 5rem;
		object-fit: contain;
		object-position: left center;
		opacity: 0.92;
	}
	:global(html:not(.dark)) .mark {
		filter: invert(1);
		opacity: 0.8;
	}
</style>
