// What is said about a person under their name. The same sentence in the panel
// at the top and on the screen the panel opens into — one place, because two
// copies of it drifted the moment one of them was corrected.

import { formatNumber, i18n, t } from '$lib/i18n';
import { count } from '$lib/say/count';
import { genreName } from '$lib/say/genre';
import type { About, Card } from '$lib/keep/types';

export function aboutArtist(c: Card): string {
	const years =
		c.year && c.end_year
			? t('count.span', { a: c.year, b: c.end_year })
			: c.year
				? t('band.since', { n: c.year })
				: null;
	const country = (i18n.locale === 'hr' && c.country_hr) || c.country;
	return [years, country, c.releases ? count(c.releases, 'releases').text : null]
		.filter(Boolean)
		.join(' · ');
}

/** Where something found out in the world can be watched instead of fetched. */
export function streamingOn(c: Card | null): string {
	return c?.owned === false && c.streaming?.length
		? t('streaming.on', { services: c.streaming.map((s) => s.name).join(', ') })
		: '';
}

/** And about a work: when it is from, how long it takes, what kind of thing it
    is. The same line in the panel at the top and on the screen it opens into. */
export function aboutWork(about: About | null): string {
	if (!about) return '';
	return [
		about.year,
		about.runtime_min ? t('play.minutes', { n: formatNumber(about.runtime_min) }) : null,
		...(about.genres ?? []).map(genreName)
	]
		.filter(Boolean)
		.join(' · ');
}
