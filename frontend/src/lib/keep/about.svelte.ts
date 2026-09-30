// What a record is: its paragraph, who put it out and what kind of music it is.
//
// Asked for after the music has started, never before it: the answer may go to
// Wikipedia and nobody presses play to wait. One record at a time, because one
// is playing at a time, and the same record is not asked about twice.

import { request } from '$lib/kit';

export type Told = {
	id: number;
	title: string;
	release_date: string | null;
	description: string;
	label: string;
	genres: string[];
};

const NOTHING: Told = {
	id: 0,
	title: '',
	release_date: null,
	description: '',
	label: '',
	genres: []
};

class AboutState {
	private known = $state(new Map<number, Told>());
	private asking = 0;

	/** everything the catalogue has to say about a record */
	told(release: number | null | undefined): Told {
		return (release ? this.known.get(release) : null) ?? NOTHING;
	}

	/** and the paragraph on its own, which is what most screens want */
	of(release: number | null | undefined): string {
		return this.told(release).description;
	}

	async ask(release: number | null | undefined) {
		if (!release || this.known.has(release) || this.asking === release) return;
		this.asking = release;
		const told = await request<Told>(`/api/library/release/${release}/about`);
		this.asking = 0;
		if (!told) return;
		this.known = new Map(this.known).set(release, { ...NOTHING, ...told });
	}
}

export const about = new AboutState();
