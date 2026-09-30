<script lang="ts">
	// A shelf of records: the sleeves themselves, at the size a sleeve is worth
	// looking at, walked sideways under a heading that says what they are.
	//
	// A column of pills said the same things in less room and read as a form. A
	// record is a picture — it is how anybody finds the one they meant — and ten
	// feet away a picture is the only thing that carries at all. The row shows
	// as many as the screen holds and fades the side that has more; the ring
	// carries past the edge, which is what `sideways` is marking.

	import { art } from '$lib/ask/art';
	import { sideways } from './sideways';
	import { SLEEVE } from './cells';

	type Sleeve = {
		id: number;
		title: string;
		/** the year, how many songs — whatever is worth one small line */
		quiet?: string;
		cover?: string | null;
		/** a record the house does not hold: named and dimmed, never hidden */
		away?: boolean;
	};

	let {
		label,
		note = '',
		sleeves,
		onpick,
		onat
	}: {
		label: string;
		note?: string;
		sleeves: Sleeve[];
		onpick: (sleeve: Sleeve) => void;
		/** which record the remote is standing on */
		onat?: (sleeve: Sleeve) => void;
	} = $props();
</script>

<section class="shelf">
	<h2>
		{label}
		{#if note}<span class="note">{note}</span>{/if}
	</h2>
	<ul
		class="row"
		use:sideways
		style:--sleeve="{SLEEVE.cell}px"
		style:--air="{SLEEVE.gap}px"
	>
		{#each sleeves as sleeve (sleeve.id)}
			<li>
				<button
					class="sleeve"
					class:away={sleeve.away}
					onclick={() => onpick(sleeve)}
					onfocus={() => onat?.(sleeve)}
				>
					<span class="art">
						{#if sleeve.cover}<img src={art(sleeve.cover, 320)} alt="" />{/if}
					</span>
					<span class="name">{sleeve.title}</span>
					{#if sleeve.quiet}<span class="quiet">{sleeve.quiet}</span>{/if}
				</button>
			</li>
		{/each}
	</ul>
</section>

<style>
	.shelf {
		min-width: 0;
	}
	h2 {
		display: flex;
		align-items: baseline;
		gap: 0.7rem;
		margin: 0 0 0.6rem;
		font-size: var(--fs-s);
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.note {
		font-size: var(--fs-s);
		font-weight: 400;
		letter-spacing: 0;
		text-transform: none;
		opacity: 0.75;
	}
	.row {
		display: flex;
		flex-wrap: nowrap;
		gap: var(--air);
		margin: 0;
		/* the ring stands outside the sleeve it is around, and a row that clips
		   its own overflow would cut it off along the top */
		padding: 0.6rem 0.3rem 0.4rem;
		list-style: none;
		overflow-x: auto;
		scrollbar-width: none;
		scroll-padding-inline: 0.5rem;
	}
	.row::-webkit-scrollbar {
		display: none;
	}
	li {
		flex: none;
		width: var(--sleeve);
		min-width: 0;
	}
	.sleeve {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		width: 100%;
		min-width: 0;
		padding: 0;
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	/* the sleeve under the ring lifts out of the shelf; the rest stay flat and
	   go quiet, the way a row of posters does when one of them is being chosen */
	.art {
		display: block;
		width: 100%;
		aspect-ratio: 1;
		border-radius: var(--radius-m, 12px);
		background: var(--surface-2);
		box-shadow: var(--shadow-l);
		overflow: hidden;
		transition:
			transform 140ms ease,
			box-shadow 140ms ease;
	}
	.art img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.sleeve:is(:focus, :focus-visible) .art {
		transform: scale(1.06);
		box-shadow: var(--shadow-xl);
	}
	.row:focus-within .sleeve:not(:focus-visible) .art {
		opacity: 0.55;
		transition: opacity 140ms ease;
	}
	/* Two lines, the same as every other tile in the app: the average record
	   title is longer than a 144px cell holds, so one line made `Kost U Gr…`
	   the rule rather than the exception. The room for both is kept whether or
	   not this title needs it, so the shelf stays one straight line of covers —
	   and the sleeve under the ring shows the whole of its title, however many
	   lines that takes, because that is the one being read. */
	.name {
		font-size: var(--fs-m);
		font-weight: 600;
		line-height: 1.25;
		min-height: 2.5em;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}
	.sleeve:is(:focus, :focus-visible) .name {
		-webkit-line-clamp: none;
		line-clamp: none;
		overflow: visible;
	}
	.quiet {
		font-size: var(--fs-s);
		color: var(--muted);
	}
	/* a record the house does not hold is on the shelf as a name, not as a gap */
	.away .art {
		box-shadow: none;
		opacity: 0.45;
	}
	.away .name {
		color: var(--muted);
	}
</style>
