// A person's music favourites.  The Player owns this preference; the Library
// remains the source for the track cards themselves.  Kept once for the whole
// browser so twelve rows of an album do not make twelve identical requests.

import { request } from '$lib/kit';
import { watching } from './watching.svelte';

type FavoriteList = { tracks: Array<{ id: number }> };

class Favorites {
	ids = $state<Set<number> | null>(null);
	#person = '';
	#busy = $state(new Set<number>());

	get ready(): boolean {
		return this.ids !== null && this.#person === watching.person;
	}

	has(trackId: number): boolean {
		return this.ids?.has(trackId) ?? false;
	}

	busy(trackId: number): boolean {
		return this.#busy.has(trackId);
	}

	async ask() {
		const person = watching.person;
		if (!person) {
			this.#person = '';
			this.ids = null;
			return;
		}
		if (this.ready) return;
		this.#person = person;
		this.ids = null;
		const found = await request<FavoriteList>('/api/music/favorites');
		// An account could have changed while this request was in flight. Its
		// preference list must never briefly appear under the next person's name.
		if (this.#person === person && watching.person === person && found) {
			this.ids = new Set(found.tracks.map((track) => track.id));
		}
	}

	async toggle(trackId: number) {
		const person = watching.person;
		const before = this.ids;
		if (!person || !before || this.busy(trackId)) return;
		const held = before.has(trackId);
		this.#busy = new Set(this.#busy).add(trackId);
		const next = new Set(before);
		if (held) next.delete(trackId);
		else next.add(trackId);
		this.ids = next;
		const said = await request(`/api/music/favorites/${trackId}`, {
			method: held ? 'DELETE' : 'PUT'
		});
		if (said === null && this.#person === person && watching.person === person) this.ids = before;
		const done = new Set(this.#busy);
		done.delete(trackId);
		this.#busy = done;
	}
}

export const favorites = new Favorites();
