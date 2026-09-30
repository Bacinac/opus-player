// TMDB and Deezer both name their genres in English, and neither says them in
// Croatian, so the closed lists of them are translated here rather than
// fetched. A genre either adds later has no key yet and shows under its English
// name, which is a word a reader can still use — never a raw key.

import { t } from '$lib/i18n';

const slug = (name: string) => name.toLowerCase().replace(/[^a-z]/g, '');

function named(key: string, name: string): string {
	const said = t(key as never);
	return said === key ? name : said;
}

export const genreName = (name: string) => named(`genre.${slug(name)}`, name);

/** a record's genre: music has its own list, and a film's "Music" is not one */
export const musicGenreName = (name: string) => named(`music.genre.${slug(name)}`, name);
