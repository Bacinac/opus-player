/* What the player asks about the household's photographs.
 *
 * All of it goes through the player's own backend, which asks the library — the
 * pictures never cross the LAN twice and no page ever holds a key to anything.
 * Nothing here keeps a copy: the library is the one that knows, and a shelf that
 * cached would be a shelf that could be wrong about a photograph taken an hour
 * ago. */

import { request } from '$lib/kit';

export type Face = {
	id: number;
	name: string;
	given_name?: string;
	born_on?: string | null;
	cover?: number | null;
	// how many faces of them the library has gathered, which is the only count
	// it keeps about a person — a photograph with three of their faces in it is
	// three faces and one photograph
	faces?: number;
	years?: number[];
	// the roster's account whose face this is, and whether the household counts
	// them as family
	account?: string | null;
	family?: boolean;
};

export type Where = {
	place: string;
	country?: string;
	photographs: number;
	/** where to put the pin: the middle of what was photographed there, not the
	 *  middle of the town. Absent for a place somebody typed rather than one the
	 *  coordinates worked out. */
	at?: { lat: number; lon: number } | null;
	first?: string | null;
	last?: string | null;
	/** the newest photograph taken there, which stands for the place */
	cover?: string | null;
	cover_turn?: number;
};

export type Month = { month: string; count: number };

const list = <T>(said: unknown, key: string): T[] =>
	Array.isArray(said) ? (said as T[]) : (((said as Record<string, unknown>)?.[key] as T[]) ?? []);

export const months = async (): Promise<{ months: Month[]; total: number }> => {
	const said = (await request('/api/photos/timeline/buckets')) as
		| { months?: Month[]; total?: number; undated?: number }
		| null;
	// the undated belong to the library even though they belong to no month
	return { months: said?.months ?? [], total: (said?.total ?? 0) + (said?.undated ?? 0) };
};

export const faces = async (): Promise<Face[]> =>
	list<Face>(await request('/api/photos/people'), 'people');

export const wheres = async (): Promise<Where[]> =>
	list<Where>(await request('/api/photos/places'), 'places');
