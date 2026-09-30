import { opened } from '$lib/keep/opened.svelte';

// Where to find more of what a shelf holds.
//
// Films are looked for from the films, series from the series, music from the
// stations and from what the catalogue offers — one screen holding all three
// had nothing in common with itself. The
// list belongs to the shelf, so it lives beside the shelf's own panel rather
// than in the navigation: a section is a place, and these are questions you ask
// once you are standing in it.

export const WAYS: Record<string, readonly string[]> = {
	movies: ['trending', 'awards', 'genres', 'actors', 'studios', 'spell'],
	series: ['trending', 'awards', 'genres', 'actors', 'studios', 'spell'],
	music: ['radio', 'offered', 'spell'],
	// The photographs' views ARE its ways: the same row of pills every other
	// section carries, saying the same kind of thing. They were drawn inside the
	// section as a private strip, which is why walking onto it in the menu
	// answered with nothing while every other section answered with its buttons.
	//
	// Today leads, and is where the section opens: it is the one question a
	// timeline cannot answer, and it is what somebody opening the photographs
	// usually came for.
	photos: ['today', 'time', 'people', 'places', 'guess', 'spell']
};

/** The ways into a section.
 *
 *  Every one of them is a way of looking at what the household holds. The vault
 *  was one of them and is not: it is one person's own corner, kept rather than
 *  browsed, and a row of pills that says Years · People · Places · Vault offers
 *  the private one as though it were a fourth way of reading the family album.
 *  It stands with the rest of what belongs to a person, on their settings. */
export function waysOf(section: string): readonly string[] {
	return shown(WAYS[section] ?? []);
}

// On a television the section's own link opens what this person was in the
// middle of, and everything else is a page of its own linked beneath it in the
// menu. One page stacked with every row put the whole wall five presses down,
// and a head scrolling past rows cut their titles in half on the way.
export const DISCOVER: Record<string, readonly string[]> = {
	movies: ['trending', 'awards', 'genres', 'actors', 'studios'],
	series: ['trending', 'awards', 'genres', 'actors', 'studios'],
	music: ['offered', 'releases', 'similar']
};

// the ways that stand on what the installation added to the Library, shown
// only where it did
const INSTALLED = ['offered', 'similar'];
const shown = (ways: readonly string[]) =>
	ways.filter((way) => !INSTALLED.includes(way) || opened.music.includes(way));

/** The discovery questions of a section, as this installation answers them. */
export function discoverOf(section: string): readonly string[] {
	return shown(DISCOVER[section] ?? []);
}

export const PAGES: Record<string, readonly string[]> = {
	movies: ['all', 'discover'],
	series: ['all', 'discover'],
	music: ['all', 'discover'],
	photos: ['time', 'people', 'places', 'guess', 'spell']
};

/** The page of a section an address is on, as the menu names it: every
 *  discovery question — a person or a studio asked for from a film included —
 *  is Discover, and no page at all is the section's own. */
/** The section a page belongs to, which is the page that answers `?person=`
 *  and `?company=`: a series' own page asked it heard nothing. */
export function sectionOf(pathname: string): string {
	return `/${pathname.split('/')[1] ?? ''}`;
}

export function pageOf(asked: URLSearchParams): string {
	const find = asked.get('find');
	if (find && [...Object.values(DISCOVER).flat(), 'search'].includes(find)) return 'discover';
	if (find) return find;
	return ['person', 'company', 'genre'].some((k) => asked.get(k)) ? 'discover' : '';
}

/** What the menu calls a page: the whole shelf is named the way its wall is. */
export const pageWord = (section: string, page: string) =>
	page === 'all' ? `wall.${section}` : `find.${page}`;

/** The pages under a section where a person can see them all at once — down
 *  the side of a wide screen, as pills on a phone: the whole shelf first, then
 *  every way to look for more. The section's own link is what they were in the
 *  middle of, as it is on a television. */
export function pagesUnder(section: string): readonly string[] {
	return [...(PAGES[section]?.includes('all') ? ['all'] : []), ...waysOf(section)];
}
