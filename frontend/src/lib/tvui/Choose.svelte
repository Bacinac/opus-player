<script lang="ts" module>
	export type Option = {
		key: string;
		label: string;
		/** a fact about the thing behind the choice — how many, how long, what year */
		note?: string;
		/** a mark that says it better than the word, which then only names it */
		image?: string;
	};
</script>

<script lang="ts">
	// One answer out of a few (or several, chosen among), for a remote.
	//
	// Two shapes, because the surface reads them differently and only two ways:
	// a LIST is walked one item at a time — sound tracks, subtitles, an order
	// for a shelf, a language; a ROW is seen whole — seasons, themes, pills in
	// a line that wraps. One option model under both, which is what the six
	// mechanisms this replaces did not have.
	//
	// Not a <select>: a native dropdown on a television opens a menu drawn by
	// the system, and a D-pad either cannot reach into it or cannot get out of
	// it again.
	//
	// `over` stands the list over the screen: its own ground, and its own Held,
	// so BACK closes the list and not the page behind it. `said` is the closed
	// shape — what the control shows while the list is away; pressing it opens
	// the list over the page. Neither is a style: they are where the thing is.

	import Held from './Held.svelte';
	import Press from './Press.svelte';
	import { t } from '$lib/i18n';
	import { Icon } from '$lib/kit';

	let {
		options,
		chosen = $bindable([]),
		refused = $bindable([]),
		cycle = false,
		many = false,
		all = '',
		as = 'list',
		over = false,
		said,
		onpick,
		onclose
	}: {
		options: Option[];
		/** the keys chosen, in the order they were chosen */
		chosen?: string[];
		/** cycle only: the keys held out */
		refused?: string[];
		/** row shape: a press walks at rest → chosen → refused → at rest, so
		 *  a filter can say "only these" and "not these" at once */
		cycle?: boolean;
		many?: boolean;
		/** the label of the take-everything pill; absent means no such pill.
		 *  Row shape only — taking everything is a row's kind of choice. */
		all?: string;
		as?: 'list' | 'row';
		over?: boolean;
		/** the closed shape's fallback label, when nothing chosen answers */
		said?: string;
		/** told which key was pressed, for a choice that acts rather than
		 *  merely being recorded */
		onpick?: (key: string) => void;
		/** over only: BACK (or picking) put the list away */
		onclose?: () => void;
	} = $props();

	const every = $derived(options.length > 0 && chosen.length === options.length);
	const saying = $derived.by(() => {
		const named = options.filter((o) => chosen.includes(o.key)).map((o) => o.label);
		if (named.length > 2)
			return t('choose.andMore', { names: named.slice(0, 2).join(', '), more: named.length - 2 });
		return named.join(', ') || (said ?? '');
	});

	let open = $state(false);
	let drop = $state<HTMLElement>();
	let up = $state(false);
	let below = $state(0);
	let above = $state(0);

	// The list opens where the screen has room for it: below the control, or
	// above it when below is too short for it and above is not. What is left
	// over still scrolls inside the list, never off the screen or under the bar.
	$effect(() => {
		if (!open || !drop) return;
		const at = drop.getBoundingClientRect();
		below = innerHeight - at.bottom;
		above = at.top;
		up = false;
		const frame = requestAnimationFrame(() => {
			const list = drop?.querySelector<HTMLElement>('.choices');
			if (!list) return;
			if (list.scrollHeight > list.clientHeight && above > below) up = true;
			requestAnimationFrame(() =>
				list.querySelector('button.on')?.scrollIntoView({ block: 'nearest' })
			);
		});
		return () => cancelAnimationFrame(frame);
	});

	$effect(() => {
		if (!open) return;
		const away = (event: PointerEvent) => {
			if (!drop?.contains(event.target as Node)) shut();
		};
		window.addEventListener('pointerdown', away, true);
		return () => window.removeEventListener('pointerdown', away, true);
	});

	function press(key: string) {
		if (cycle) {
			if (chosen.includes(key)) {
				chosen = chosen.filter((k) => k !== key);
				refused = [...refused, key];
			} else if (refused.includes(key)) refused = refused.filter((k) => k !== key);
			else chosen = [...chosen, key];
		} else if (!many) chosen = [key];
		else chosen = chosen.includes(key) ? chosen.filter((k) => k !== key) : [...chosen, key];
		if (open && !many) shut();
		onpick?.(key);
	}

	function named(option: Option): string {
		if (!cycle) return option.label;
		if (chosen.includes(option.key)) return t('choose.only', { name: option.label });
		if (refused.includes(option.key)) return t('choose.without', { name: option.label });
		return option.label;
	}

	function shut() {
		open = false;
		onclose?.();
	}
</script>

{#snippet list()}
	<div class="choices" class:over={over || open}>
		{#each options as option (option.key)}
			<button data-choice class:on={chosen.includes(option.key)} onclick={() => press(option.key)}>
				<span class="tick">{#if chosen.includes(option.key)}<Icon name="check" size={14} />{/if}</span>
				<span class="what">
					{option.label}{#if option.note}<span class="note">{option.note}</span>{/if}
				</span>
			</button>
		{/each}
	</div>
{/snippet}

{#if said !== undefined}
	<span
		class="drop"
		class:up
		bind:this={drop}
		style:--below="{below}px"
		style:--above="{above}px"
	>
		<Press onclick={() => (open ? shut() : (open = true))}>{saying}</Press>
		{#if open}
			<Held onclose={() => (shut(), true)} still={false} first=".choices button.on">
				{@render list()}
			</Held>
		{/if}
	</span>
{:else if as === 'row'}
	<div class="picks">
		{#if many && all}
			<Press
				tone="pill"
				on={every}
				onclick={() => (chosen = every ? [] : options.map((o) => o.key))}
			>
				{all}
			</Press>
		{/if}
		{#each options as option (option.key)}
			<Press
				tone="pill"
				on={chosen.includes(option.key)}
				refused={refused.includes(option.key)}
				title={option.image || cycle ? named(option) : undefined}
				label={cycle ? named(option) : undefined}
				onclick={() => press(option.key)}
			>
				{#if option.image}
					<img class="mark" src={option.image} alt={option.label} />
				{:else}
					{option.label}
				{/if}{#if option.note}<span class="note">{option.note}</span>{/if}
			</Press>
		{/each}
	</div>
{:else if over}
	<Held onclose={() => (shut(), true)} still={false} first=".choices button.on">
		{@render list()}
	</Held>
{:else}
	{@render list()}
{/if}

<style>
	.choices {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		min-width: 0;
	}
	.choices.over {
		max-height: 60vh;
		overflow-y: auto;
		padding: 0.3rem;
		border: var(--card-line, 1px solid var(--on-picture-faint));
		border-radius: var(--card-radius, 12px);
		background: var(--card-ground, var(--surface));
		backdrop-filter: blur(14px);
		box-shadow: var(--shadow-l);
	}
	.choices button {
		display: flex;
		align-items: center;
		gap: 0.2rem;
		padding: 0.35rem 0.7rem;
		border: none;
		border-radius: var(--radius-s);
		background: none;
		color: var(--muted);
		font: inherit;
		font-size: var(--fs-l);
		text-align: left;
		white-space: nowrap;
		cursor: pointer;
		outline: none;
	}
	.over button {
		font-size: var(--fs-l);
		padding: 0.5rem 0.9rem;
	}
	.choices button.on {
		color: var(--text);
	}
	.choices button:hover,
	.choices button:focus-visible {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
		color: var(--bright, var(--text));
	}
	/* the tick keeps its column whether or not it is there, so the words do not
	   step sideways as the answer changes */
	.tick {
		display: inline-grid;
		place-items: center;
		width: 1rem;
		color: currentColor;
	}
	.what {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.note {
		font-size: 0.82em;
		opacity: 0.7;
		margin-left: 0.4rem;
	}

	.picks {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.mark {
		display: block;
		width: 1.9rem;
		height: 1.9rem;
		border-radius: 0.4rem;
	}

	.drop {
		position: relative;
		display: inline-block;
	}
	.drop :global(.held) {
		position: absolute;
		top: calc(100% + 0.3rem);
		left: 0;
		z-index: 20;
		min-width: 100%;
	}
	.drop.up :global(.held) {
		top: auto;
		bottom: calc(100% + 0.3rem);
	}
	.drop .choices.over {
		max-height: calc(
			var(--below) - 0.3rem - var(--shell-bar-h, 0px) - env(safe-area-inset-bottom) - 0.75rem
		);
	}
	.drop.up .choices.over {
		max-height: calc(var(--above) - 0.3rem - env(safe-area-inset-top) - 0.75rem);
	}
</style>
