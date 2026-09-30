// How this viewer wants each shelf arranged.
//
// Kept here rather than asked of the catalogue: the library owns what a thing
// IS, and the order somebody walks past it in is theirs. One answer per shelf,
// because films and artists do not want the same one — a wall of faces is read
// alphabetically and a wall of films is usually read by what turned up last.

import { json, request } from '$lib/kit';

export const ORDERS = ['added', 'title', 'year'] as const;
export type Order = (typeof ORDERS)[number];
export type Way = 'asc' | 'desc';

/** Which way round each of them reads when it is first chosen: newest, A first,
 *  most recent year. Pressing the one you are already on turns it over. */
const NATURAL: Record<Order, Way> = { added: 'desc', title: 'asc', year: 'desc' };

/** Which way an option would go if it were chosen now — so it can say so before
 *  it is chosen, rather than announcing itself in the abstract and making the
 *  first press mean nothing but "and which way round". */
export const natural = (order: Order): Way => NATURAL[order];

export const SHELVES = ['movies', 'series', 'music'] as const;

class Shelf {
	chosen = $state<Record<string, string>>({});
	who = $state<string | null>(null);
	/** a television let in with nobody picked on it keeps its own */
	box = false;
	adopt(profile: string | null, box: boolean, stored: string) {
		this.who = profile;
		this.box = box;
		try {
			const parsed = stored ? JSON.parse(stored) : {};
			this.chosen = typeof parsed === 'object' && parsed ? parsed : {};
		} catch {
			this.chosen = {};
		}
	}

	of(shelf: string): { order: Order; way: Way } {
		// a wall of faces is read alphabetically; a wall of films by what turned
		// up last — the file's own opening line, which the code had not kept
		const [order, way] = (this.chosen[shelf] ?? (shelf === 'music' ? 'title' : 'added')).split(':');
		const key = ((ORDERS as readonly string[]).includes(order) ? order : 'added') as Order;
		return { order: key, way: (way === 'asc' || way === 'desc' ? way : NATURAL[key]) as Way };
	}

	/** Choosing what is already chosen turns it over, which is the only place a
	 *  second press has to put "the other way round". */
	async choose(shelf: string, order: Order) {
		const now = this.of(shelf);
		const way: Way =
			now.order === order ? (now.way === 'asc' ? 'desc' : 'asc') : NATURAL[order];
		this.chosen = { ...this.chosen, [shelf]: `${order}:${way}` };
		await this.keep({ shelf_orders: JSON.stringify(this.chosen) });
	}

	private async keep(change: Record<string, string>) {
		const body = json(change, 'PATCH');
		if (this.who !== null) await request(`/api/users/${encodeURIComponent(this.who)}`, body);
		else if (this.box) await request('/api/box', body);
	}
}

export const shelf = new Shelf();
