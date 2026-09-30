// How many of a thing, written the way the reader counts and painted the way
// the product paints that kind. Croatian takes three forms and English two; the
// rule lives in the shared layer and the keys are named after the thing, so a
// screen asks for a count and gets a badge.

import { plural } from '$lib/i18n';
import type { TagTone } from '$lib/kit';
import type { Kind } from '$lib/opus';

export type Count = { text: string; tone?: TagTone; kind?: Kind; icon: string };

// what is counted, and what it is counted in: a shelf's own kind carries the
// kind's colour, and the second measure of it stays a plain fact
const LOOK: Record<string, { tone?: TagTone; kind?: Kind; icon: string }> = {
	movies: { kind: 'film', icon: 'film' },
	hours: { kind: 'film', icon: 'clock' },
	series: { kind: 'series', icon: 'screen' },
	episodes: { kind: 'series', icon: 'list' },
	artists: { kind: 'music', icon: 'note' },
	stations: { kind: 'music', icon: 'sound' },
	countries: { tone: 'fact', icon: 'pin' },
	releases: { kind: 'music', icon: 'disc' },
	songs: { kind: 'music', icon: 'note' },
	photos: { kind: 'photos', icon: 'photo' },
	people: { kind: 'photos', icon: 'people' },
	places: { tone: 'fact', icon: 'pin' }
};

export function count(n: number, of: string): Count {
	const text = plural(n, `count.${of}.one`, `count.${of}.few`, `count.${of}.many`);
	return { text, ...(LOOK[of] ?? { tone: 'fact' as TagTone, icon: '' }) };
}

/** Something true that is not a count of anything — the years a shelf runs
    between, which is how somebody browsing by decade reads it. */
export function fact(text: string, icon: string, tone: TagTone = 'fact'): Count {
	return { text, icon, tone };
}
