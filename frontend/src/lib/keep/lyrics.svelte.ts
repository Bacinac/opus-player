// The words to what is playing.
//
// Asked of the library once per song and kept for as long as the page lives,
// because a record is put on and then played through: going back a track must
// not go back to the network. Which line is being sung is worked out here as
// well — it is the same question every screen showing them would otherwise
// answer for itself.

import { request } from '$lib/kit';

export type Line = { at: number; text: string };

export type Words = {
	source: string;
	instrumental: boolean;
	lines: Line[];
	plain: string;
};

const held = new Map<number, Words>();

/** Two screens read words at once: the bar, which reads what is playing, and a
 *  record's own page, which reads whatever the remote is standing on. One of
 *  them would otherwise take the words out from under the other, so each keeps
 *  its own place in the book — and they share the map above, so the second one
 *  to want a song costs nothing. */
export class LyricsState {
	words = $state<Words | null>(null);
	/** the library could not be asked, which is not the same as a song with no
	    words — said outright, because a screen that shows "no lyrics" for a
	    library that is simply unreachable is a screen that lies quietly */
	failed = $state(false);
	/** the song the words belong to; a slow answer that arrives after the record
	    has moved on is not the words to what is playing now */
	trackId = $state<number | null>(null);
	loading = $state(false);

	/** A record playing in the house that OPUS did not put on is known by its
	 *  title and nothing else — the streamer reports words, not identities, so
	 *  the song carries no catalogue id. There is nothing to look words up by,
	 *  and asking anyway is a 404 that reads on the screen as a catalogue that
	 *  is down. Said here rather than at each screen that asks. */
	get known(): boolean {
		return (this.trackId ?? -1) >= 0;
	}

	async load(id: number | null, refresh = false) {
		this.trackId = id;
		this.failed = false;
		if (id === null || id < 0) {
			this.words = null;
			this.loading = false;
			return;
		}
		const kept = held.get(id);
		if (kept && !refresh) {
			this.words = kept;
			this.failed = false;
			this.loading = false;
			return;
		}
		this.words = null;
		this.failed = false;
		this.loading = true;
		// said by the screen that shows the words, not as a toast over the music
		const said = await request<Words>(`/api/play/track/${id}/lyrics${refresh ? '?refresh=1' : ''}`, {}, {
			failed: () => {}
		});
		if (this.trackId !== id) return;
		if (said) {
			held.set(id, said);
			this.words = said;
		} else {
			this.failed = true;
		}
		this.loading = false;
	}

	get timed(): boolean {
		return (this.words?.lines.length ?? 0) > 0;
	}

	/** The line being sung at this moment: the last one whose time has passed.
	 *  Walked from the end rather than searched from the start, because that is
	 *  the answer four times a second and the tail is where it always is. */
	at(seconds: number): number {
		const lines = this.words?.lines;
		if (!lines?.length) return -1;
		for (let i = lines.length - 1; i >= 0; i--) {
			if (lines[i].at <= seconds) return i;
		}
		return -1;
	}
}

export const lyrics = new LyricsState();

/** Which songs on a record have words at all — the mark beside a song, which
 *  is drawn before anybody presses it. The library is asked once for the whole
 *  record: it answers from what it has already looked up and looks up the rest,
 *  so the second time a record is opened the marks are there at once. A song it
 *  could not ask about is named apart and left unmarked, because "no words" and
 *  "could not look" are not the same thing to say about a song. */
class AlbumWordsState {
	have = $state<ReadonlySet<number>>(new Set());
	/** the record these marks belong to; marks that arrive after the page has
	    moved on belong to a record nobody is looking at */
	releaseId = $state<number | null>(null);

	async ask(id: number | null) {
		this.releaseId = id;
		if (id === null) {
			this.have = new Set();
			return;
		}
		const kept = marked.get(id);
		if (kept) {
			this.have = kept;
			return;
		}
		this.have = new Set();
		const said = await request<{ words: number[]; unknown: number[] }>(
			`/api/play/release/${id}/lyrics`,
			{},
			{ failed: () => {} }
		);
		if (!said) return;
		const found = new Set(said.words);
		// a record half of which could not be looked up is not worth remembering
		// as the answer: the next time it is opened, the rest is asked for again
		if (!said.unknown.length) marked.set(id, found);
		if (this.releaseId === id) this.have = found;
	}
}

const marked = new Map<number, ReadonlySet<number>>();

export const albumWords = new AlbumWordsState();
