<script lang="ts">
	// What the remote is on, said in words over its own picture.
	//
	// No box: the picture behind the whole screen is the ground, and the words
	// lie on it. That is what the ten-foot interfaces this is modelled on do —
	// the top fifth of the screen belongs to the thing being looked at, and the
	// shelf starts below it.
	//
	// Opened, it becomes what those skins call the info view: the poster beside
	// the words, both large enough to read from a sofa.
	//
	// On a television the picture does not stop at the panel: Ground lays the
	// same fanart behind the whole page, and this one draws its own copy at the
	// size of the screen rather than the size of the band — one address, two
	// draws, lined up on the viewport, so the panel's edge is a change of
	// brightness rather than a seam.

	import { hero } from '$lib/keep/hero.svelte';
	import { preview } from '$lib/keep/preview.svelte';
	import { shelves } from '$lib/keep/shelves.svelte';
	import { pageWord, pagesUnder } from '$lib/say/ways';
	import { goto } from '$app/navigation';
	import { surface } from '$lib/keep/surface.svelte';
	import { ground } from '$lib/ask/art';
	import { tint } from '$lib/keep/tint';
	import { genreName } from '$lib/say/genre';
	import { Icon, PageHead, narrow } from '$lib/kit';
	import { me } from '$lib/opus';
	import { type Count } from '$lib/say/count';
	import { aboutArtist, streamingOn } from '$lib/say/facts';
	import { duration, formatNumber, t } from '$lib/i18n';
	import Press from '$lib/tvui/Press.svelte';

	/** what the panel says when nothing on the screen is being pointed at: the
	    shelf you are standing at, and how much is on it. A panel that goes blank
	    the moment focus leaves a poster is a fifth of the screen saying nothing. */
	let {
		rest = null,
		ways = [],
		onway,
		on = '',
		section = '',
		tells = true
	}: {
		rest?: { counts: Count[] } | null;
		/** where to find more of what this shelf holds — the shelf's own
		 *  questions, standing with the shelf's own count rather than in the
		 *  navigation, which is a list of places and not of questions */
		ways?: readonly string[];
		onway?: (which: string) => void;
		/** the way that is CURRENT, where the ways are views rather than
		 *  questions — the photographs' views live here so that section opens
		 *  the same way every other one does */
		on?: string;
		/** whose ways they are, which is what names the whole shelf among them */
		section?: string;
		/** Whether this section has anything to say about what the ring is on.
		 *  The counts are the same head everywhere; the line under them is the
		 *  detail, and it costs five lines of reserved screen whether or not
		 *  there is a word to put in it. A photograph has no description — its
		 *  own caption says whose day it was — so that section keeps the counts
		 *  and drops the rest. */
		tells?: boolean;
	} = $props();

	const card = $derived(hero.card);

	// A section the remote is passing in the menu is a question about that
	// section: the panel answers it where it answers everything else, and
	// answers at once — the shelf itself is not fetched to be counted.
	const passing = $derived(preview.section);
	const said = $derived.by(() => {
		// The home screen is not a shelf. What it holds is the whole library and
		// the page itself is what counts that, so asked about home the panel
		// answers with the page's own answer — `/api/shelves` has a row for each
		// shelf and none for home, and asking it anyway is how the first screen
		// of this surface ended up with no counts on it at all.
		if (passing && passing !== 'home') {
			return {
				counts: shelves.of(passing),
				// a television lists a section's pages under it in the menu
				ways: surface.isTv || !narrow.current ? [] : pagesUnder(passing)
			};
		}
		return rest ? { ...rest, ways } : null;
	});

	$effect(() => {
		void shelves.ask();
	});
	// An artist has no backdrop; their own face is the only picture of them, and
	// it is thrown so far out of focus that the small copy is the one to ask for
	// — a face blurred fifty pixels does not get sharper for being fetched at a
	// thousand. Which picture that is, and when there is none, is one decision
	// and it is made in one place, because the ground behind the page makes it
	// too.
	// the same picture the ground is drawing, not the one the panel is
	// describing. They were two addresses: the band went unlit the moment the
	// remote left a poster while the ground kept the picture, and an opaque band
	// over a full-bleed fanart is a hard seam across the top of the screen.
	const art = $derived(ground(hero.behind));
	const opened = $derived(hero.open);

	$effect(() => {
		hero.arrive();
		return () => hero.leave();
	});

	// and the one colour on this surface that moves comes off that picture
	$effect(() => {
		if (!surface.isTv) return;
		if (art) tint.from(art);
		else tint.rest();
		return () => tint.rest();
	});

	// the words keep the top of the screen, so a row arrowed onto must stop
	// below them rather than slide underneath
	$effect(() => {
		if (opened) return;
		document.documentElement.classList.add('has-hero');
		return () => document.documentElement.classList.remove('has-hero');
	});

	// opened it is taller, and what is listed under it has to clear that too
	$effect(() => {
		document.documentElement.classList.toggle('hero-open', opened);
		return () => document.documentElement.classList.remove('hero-open');
	});

	const facts = $derived.by(() => {
		const c = card;
		if (!c) return '';
		if (c.kind === 'artist') return aboutArtist(c);
		// a song is not a year and a genre: what there is to say about it beyond
		// whose record it is on is how long it lasts
		if (c.kind === 'track') return duration(c.duration_s);
		return [
			c.year,
			c.runtime_min ? t('play.minutes', { n: formatNumber(c.runtime_min) }) : null,
			...(c.genres ?? []).slice(0, 3).map(genreName),
			c.directors?.length ? c.directors[0].name : null,
			streamingOn(c)
		]
			.filter(Boolean)
			.join(' · ');
	});
</script>

<!-- opened, the whole screen is about the one thing and is drawn there; this
     panel is for browsing past things.

     It draws the shared page head rather than a panel of its own. Every
     first-level page in the three modules opens the same way — what it is, how
     much of it there is, the ways into it — and this was the one place drawing
     that itself, with eleven fixed rems that stood empty on any screen where the
     remote was not pointing at anything. The picture went behind it instead; the
     line that changes as the remote moves is clamped, which is what the fixed
     height was protecting. -->
{#if !opened}
	<!-- The head does not breathe. It used to swap wholesale as the ring moved —
	     facts and ways for the shelf, then title and description for a poster —
	     and the two dressings were different heights, so every step along a row
	     pushed the shelf underneath it down and back up. The facts and the ways
	     STAY; what the ring is on is said in a slot that is always there, sized
	     for two lines whether it is holding two, one or none. -->
	<PageHead
		facts={surface.isTv ? (said?.counts ?? []) : card ? [] : (said?.counts ?? [])}
		behind={art ?? ''}
		ways={!said?.ways.length || (card && !surface.isTv) ? undefined : theWays}
		under={!tells ? undefined : surface.isTv ? aboutCard : card ? aboutCard : undefined}
	/>
{/if}

{#snippet theWays()}
	<div class="ways">
		{#each said?.ways ?? [] as which (which)}
			<Press
				tone="pill"
				on={which === on}
				onclick={() => (passing ? goto(`/${passing}?find=${which === 'spell' ? 'search' : which}`) : onway?.(which))}
				onfocus={() => hero.forget()}
			>
				{t(pageWord(passing || section, which) as never)}
			</Press>
		{/each}
	</div>
{/snippet}

{#snippet aboutCard()}
	{#if card}
		<span>
			<span class="named">{card.title}</span>
			{#if card.subtitle && card.subtitle !== card.year}{card.subtitle}{/if}
			{#if facts}<span class="facts">{facts}</span>{/if}
			{#if card.overview && !surface.isTv}<span class="overview">{card.overview}</span>{/if}
		</span>
	{/if}
{/snippet}

<style>
	/* What is left of this file's own styling: the row of ways and the two lines
	   about whatever the remote is pointing at. Everything else — the panel, the
	   picture, the scrim, the fade under it — is the shared page head's now, and
	   was eleven fixed rems of it that stood empty on any page nobody was
	   pointing at anything on. */
	.ways {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.facts,
	.overview {
		margin-left: 0.5rem;
	}
	.facts {
		color: var(--text);
	}
	.named {
		font-weight: 600;
		color: var(--bright, var(--text));
		margin-right: 0.5rem;
	}
</style>
