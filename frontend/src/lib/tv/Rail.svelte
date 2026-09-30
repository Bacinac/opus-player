<script lang="ts">
	// Navigation down the side, which is what a television does.
	//
	// A row of words across the top competes with the content for up and down —
	// the two directions a remote spends its life in. Put the sections down the
	// left and up and down belong to the shelf you are looking at, while left and
	// right are how you leave it.
	//
	// It stands. The skin this surface is modelled on slides its menu away the
	// moment the remote leaves it, and a menu that is not there is a menu you
	// have to remember — so this one keeps its column and the shelf begins after
	// it. The one thing that takes the screen from it is a film, which takes the
	// screen from everything.

	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { hero } from '$lib/keep/hero.svelte';
	import { preview } from '$lib/keep/preview.svelte';
	import { Wordmark } from '$lib/opus';
	import { focusContent } from '$lib/tv/spatial.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { t } from '$lib/i18n';
	import { PAGES, pageOf, pageWord } from '$lib/say/ways';

	let { nav }: {
		nav: { href: string; label: string }[];
	} = $props();


	/** The home screen is a section like any other as far as the picture behind
	 *  the page is concerned, and its address is the one that leaves nothing
	 *  behind when the slash is taken off. Named, so passing HOME in the menu
	 *  asks about something rather than about the empty string. */
	const shelfOf = (href: string) => href.replace('/', '') || 'home';

	/** Where you are is the section you are INSIDE, not the one address that
	 *  happens to match: a series you have opened is still Series. Home is every
	 *  path's prefix, so it is the one that has to match outright.
	 *
	 *  It compared for equality once, which was true enough while this menu was
	 *  only ever drawn on the home screen — and there the comparison could only
	 *  ever pick Home. The underline said Home while the panel above it already
	 *  said Films. */
	const inside = (href: string) =>
		href === '/'
			? page.url.pathname === '/'
			: page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);

	const onPage = $derived(pageOf(page.url.searchParams));

	/** Walking the menu goes where it walks — but only focus arriving from
	 *  another item in it. Arriving into the menu from the shelf, or being put
	 *  here by a page that has just landed, must not navigate: that is a page
	 *  change causing a focus change causing a page change, and it is how the
	 *  address wandered off on its own. replaceState, because walking a menu is
	 *  not five places you have been; keepFocus, because the ring belongs to the
	 *  menu until somebody presses. */
	function walkTo(event: FocusEvent, href: string) {
		const from = event.relatedTarget as HTMLElement | null;
		if (surface.isTv && from?.closest('nav.rail') && page.url.pathname + page.url.search !== href) {
			goto(href, { replaceState: true, keepFocus: true, noScroll: true });
		}
	}

	function enter() {
		setTimeout(focusContent, 60);
	}

	// A section's pages open when its own link is pressed, not when the ring
	// passes over it: a column that unfolds under every step is a column that
	// jumps. Right is how you go in; OK is how you ask what else is there. They
	// stay open while you are on one of them.
	let opened = $state('');
	const showsPages = (href: string) => Boolean(PAGES[shelfOf(href)]) && opened === href;
	$effect(() => {
		const current = nav.find((item) => inside(item.href))?.href ?? '';
		if (onPage) opened = current;
		else if (opened !== current) opened = '';
	});
</script>

<nav class="rail" aria-label="OPUS">
	<span class="brand"><Wordmark module="Player" /></span>

	{#each nav as item (item.href)}
		<!-- Passing over a section is asking about the section, and the answer is
		     the WHOLE right-hand side: what is on that shelf and the shelf
		     itself — so passing goes there. -->
		<a
			href={item.href}
			data-perch="section:{item.href}"
			data-own-mark
			class:in={inside(item.href)}
			class:here={inside(item.href) && !onPage}
			onfocus={(event) => {
				hero.forget();
				preview.show(shelfOf(item.href));
				walkTo(event, item.href);
			}}
			onclick={(event) => {
				if (surface.isTv && PAGES[shelfOf(item.href)]) {
					event.preventDefault();
					opened = opened === item.href ? '' : item.href;
					return;
				}
				preview.press(shelfOf(item.href));
				enter();
			}}
		>
			<span class="what">{item.label}</span>
		</a>
		<!-- the pages of the section you are in, and only of that one: four
		     sections with all of theirs open would be a column of twenty -->
		{#if showsPages(item.href)}
			{#each PAGES[shelfOf(item.href)] ?? [] as one (one)}
				{@const href = `${item.href}?find=${one}`}
				<a
					class="page"
					{href}
					data-perch="page:{href}"
					data-own-mark
					class:here={onPage === one}
					onfocus={(event) => {
						hero.forget();
						preview.show(shelfOf(item.href));
						walkTo(event, href);
					}}
					onclick={enter}
				>
					<span class="what">{t(pageWord(shelfOf(item.href), one) as never)}</span>
				</a>
			{/each}
		{/if}

	{/each}

</nav>

<style>
	.rail {
		position: fixed;
		top: 0;
		bottom: 0;
		left: 0;
		width: var(--rail-w, 11rem);
		display: flex;
		flex-direction: column;
		gap: 0;
		/* the sections begin where the shelf begins, so the screen has one line
		   across it rather than two */
		padding: var(--tenfoot-top, 1.6rem) 0.8rem 1rem;
		background: none;
		z-index: 20;
	}
	/* The picture lies behind the whole page, this column included, so the words
	   get a ground of their own — and it stops at the column, which is where the
	   shelf begins. */
	.rail::before {
		content: '';
		position: absolute;
		top: 0;
		bottom: 0;
		left: 0;
		width: 100%;
		background: linear-gradient(
			to right,
			var(--bg) 0%,
			color-mix(in srgb, var(--bg) 88%, transparent) 62%,
			transparent 100%
		);
		z-index: -1;
	}
	/* On the head's line, not above it. The panel's first row begins where the
	   head's own top padding ends, and a mark floating nine pixels higher than
	   the row beside it reads as a mark that missed. */
	.brand {
		position: absolute;
		left: var(--tenfoot-pad, 3rem);
		/* where the head's first row begins: the frame's own top air plus the
		   head's, which is Shell's --shell-main-top and PageHead's 0.9rem. Said
		   as the sum rather than as the answer, so moving either moves this. */
		top: calc(var(--shell-main-top, 1.5rem) + 0.9rem);
		display: block;
	}
	/* On the LEFT edge of the column, with the surface's own air. They stood
	   against the shelf instead — "the edge the eye is on" — which left half the
	   column, and so the whole left edge of the screen, standing empty: a
	   hundred and twenty points of nothing before the first letter. A column is
	   read from where it starts. */
	a {
		display: flex;
		align-items: center;
		justify-content: flex-start;
		gap: 0.5rem;
		/* fixed: the focused word grows inside the row, and the ones under it do
		   not move out of its way */
		height: var(--menu-row, 2.2rem);
		padding: 0 0.7rem 0 var(--tenfoot-pad, 3rem);
		color: var(--dim, var(--muted));
		text-decoration: none;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		font-size: var(--menu, var(--fs-l));
		line-height: 1;
		transition:
			font-size 150ms ease,
			color 150ms ease;
	}
	.what {
		border-bottom: 2px solid transparent;
		padding-bottom: 0.1em;
	}
	/* where you are, and where the remote is: two different things, said two
	   different ways, because on a television you are often looking at one while
	   standing on the other */
	/* where you are is underlined, the same line the remote draws under what it
	   is on — one mark, two states of it */
	a.in,
	a.here {
		color: var(--text);
	}
	/* a page of the section: the section's own word, a step in and a size down */
	a.page {
		height: var(--menu-sub-row, 1.9rem);
		padding-left: calc(var(--tenfoot-pad, 3rem) + 1rem);
		text-transform: none;
		letter-spacing: 0;
		font-size: var(--menu-sub, var(--fs-m));
		color: var(--dim, var(--muted));
	}
	a.page.here {
		color: var(--text);
	}
	a.page:focus {
		color: var(--bright, var(--text));
		font-size: var(--menu-sub, var(--fs-m));
	}
	a.here .what {
		border-bottom-color: color-mix(in srgb, var(--accent) 55%, transparent);
	}
	/* :focus, not :focus-visible. Every move here is a programmatic .focus() and
	   whether that counts as visible is the browser's own heuristic; the one mark
	   this column has cannot rest on one. */
	a:focus {
		color: var(--bright, var(--text));
		font-size: var(--menu-on, var(--fs-l));
	}
	/* the one line on this surface that is drawn in the colour of the picture */
	a:focus .what {
		border-bottom-color: var(--accent);
	}
	/* While the remote is in this column, where-you-are steps back. The two marks
	   are for looking at one place while standing on another; both lit at once is
	   the menu saying two things, neither of them the one under the remote. */
	.rail:focus-within a.here:not(:focus),
	.rail:focus-within a.in:not(:focus) {
		color: var(--dim, var(--muted));
	}
	.rail:focus-within a.here:not(:focus) .what {
		border-bottom-color: transparent;
	}
</style>
