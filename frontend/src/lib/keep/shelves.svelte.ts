// How much is on each shelf, asked once and kept.
//
// The panel says this about a shelf while the remote is merely passing its
// section in the menu, so it cannot wait for that shelf to be fetched and
// counted — walking past five sections would be five shelves loaded to answer a
// question about none of them. One answer for all of them, and the home screen
// says the same numbers the menu does.

import { request } from '#lib/kit/index.js';
import { count, fact } from '#lib/say/count.js';
import type { Count } from '#lib/say/count.js';
import { t } from '#lib/i18n/index.js';

type Shelf = {
	count: number;
	hours?: number;
	episodes?: number;
	releases?: number;
	people?: number;
	places?: number;
	countries?: number;
	span: [number, number] | null;
};

type Measure = 'hours' | 'episodes' | 'releases' | 'people' | 'countries';

// what each shelf is measured in besides the count of it; the first is the one
// the home screen says, and every shelf that can be watched or heard says how
// long that takes
const BESIDES: Record<string, Measure[]> = {
	movies: ['hours'],
	series: ['episodes', 'hours'],
	music: ['releases', 'hours'],
	photos: ['people'],
	radio: ['countries']
};

const KIND: Record<string, string> = {
	radio: 'stations',
	movies: 'movies',
	series: 'series',
	music: 'artists',
	photos: 'photos'
};

class ShelvesState {
	private held = $state<Record<string, Shelf> | null>(null);
	/** why the library could not say, when it could not */
	problem = $state('');
	private asking = false;

	get answered(): boolean {
		return this.held !== null || this.problem !== '';
	}

	async ask() {
		if (this.held || this.asking) return;
		this.asking = true;
		const said = await request<Record<string, Shelf>>('/api/shelves', {}, {
			failed: (detail) => (this.problem = detail)
		});
		this.asking = false;
		if (said) {
			this.held = said;
			this.problem = '';
		}
	}

	/** how many a shelf holds, the number its counts start with */
	countOf(section: string): number | null {
		return this.held?.[section]?.count ?? null;
	}

	/** The years a shelf runs between, for a screen that counts its own cards but
	 *  cannot work this out from them — music, whose cards are people, and whose
	 *  years would otherwise be the years the bands were formed. */
	spanOf(section: string): [number, number] | null {
		return this.held?.[section]?.span ?? null;
	}

	/** the counts a panel paints for a shelf: how many, the measures that shelf
	 *  is read in besides, and the years it runs between */
	of(section: string): Count[] {
		const shelf = this.held?.[section];
		if (!shelf?.count) return [];
		const counts = [count(shelf.count, KIND[section] ?? section)];
		for (const measure of BESIDES[section] ?? []) {
			const also = shelf[measure];
			if (also) counts.push(count(also, measure));
		}
		if (shelf.span) counts.push(fact(t('count.span', { a: shelf.span[0], b: shelf.span[1] }), 'years'));
		return counts;
	}

	/** What the whole house holds, for the screen that is not a shelf: each kind
	 *  and the one measure it is read in besides. */
	everything(sections: readonly string[]): Count[] {
		return sections.flatMap((section) => {
			const shelf = this.held?.[section];
			if (!shelf?.count) return [];
			const [measure] = BESIDES[section] ?? [];
			const also = measure && section !== 'photos' ? shelf[measure] : 0;
			return [count(shelf.count, KIND[section]), ...(also ? [count(also, measure)] : [])];
		});
	}
}

export const shelves = new ShelvesState();
