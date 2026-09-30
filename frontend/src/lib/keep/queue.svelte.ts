// What is playing, and what comes after it.
//
// Music is the one thing here that outlives the screen that started it: a film
// is a page you are on, an album is something running while you go and look at
// something else. So the queue is module state and the bar that shows it lives
// in the frame, not on the music page.

import { forget, keep, recall } from '$lib/kit';

/** Whether the television's own player is there to take a stream. It is the
    only place a surround edition can be heard: everywhere else the sound is
    decoded and folded down to two channels before it leaves the page. */
export function hasEngine(): boolean {
	return typeof window !== 'undefined' && typeof window.opusTv?.engine === 'function';
}

export type QueueTrack = {
	id: number;
	position: number;
	title: string;
	artist: string;
	album: string;
	cover_url: string | null;
	duration_s: number | null;
	// what the library knows of the file: the channel count picks the output
	// (stereo to the DAC, more to the receiver), the codec rides the cast URL
	channels?: number | null;
	/** the record it is off, so a screen can ask what that record is */
	release_id?: number | null;
	/** whose it is, so a song heard counts toward its artist */
	artist_id?: number | null;
	codec?: string | null;
	/** a station's stream, kept alive by somebody else. When it is here the
	    bytes are not ours and no ticket is asked for. */
	url?: string | null;
	/** where that station is opened from here: its own address when it is
	    https, the player's relay when it is not */
	play_url?: string | null;
	/** something with no end and no track list — a station, whoever put it on.
	    Said outright rather than guessed from a missing id: a record adopted
	    from the streamer has no id of ours either, and guessing turned an album
	    into a station with its sleeve, its songs and its words gone. */
	live?: boolean;
};

const KEPT = 'opus-player-queue';

class QueueState {
	tracks = $state<QueueTrack[]>([]);
	index = $state(0);
	playing = $state(false);
	// set by the bar's audio element; the queue owns what plays, not how
	position = $state(0);
	/** where the song is to start, for a record put back on where it was left.
	    Cleared by the bar once it has seeked, so the next song starts at nought */
	startAt = $state(0);
	/** the box is already playing this one — deliberately not reactive, because
	    the effect that would clear it is the effect that reads it */
	attached = false;
	/** told when a record goes on, so the sound can be aimed at the house
	    instead of this screen. Wired by the cast store; the pages only ever say
	    play(), no matter where it comes out. */
	autocast: (() => void) | null = null;

	get current(): QueueTrack | null {
		return this.tracks[this.index] ?? null;
	}

	get src(): string {
		return this.srcAt(this.index);
	}

	/** The address of any track in the queue, so the one after this can be
	 *  loaded while this one is still playing. */
	srcAt(index: number): string {
		const track = this.tracks[index];
		if (!track) return '';
		return track.url ? (track.play_url ?? '') : `/api/play/track/${track.id}/stream`;
	}

	/** What follows, when something does and it is a file rather than a station:
	 *  a stream has no end to run into and nothing to fade into. */
	get nextSrc(): string {
		if (!this.hasNext) return '';
		return this.tracks[this.index + 1]?.url ? '' : this.srcAt(this.index + 1);
	}

	get hasNext(): boolean {
		return this.index < this.tracks.length - 1;
	}

	/** An album, from the track that was pressed. Pressing the fourth song does
	 *  not mean playing only the fourth song — the rest of the record follows,
	 *  which is what putting a record on has always meant. */
	play(tracks: QueueTrack[], from = 0, at = 0) {
		this.tracks = tracks;
		this.index = Math.max(0, Math.min(from, tracks.length - 1));
		this.position = at;
		this.startAt = at;
		this.playing = true;
		this.attached = false;
		this.keep();
		this.autocast?.();
	}

	/** What the box is already playing when the page comes back.
	 *
	 *  The engine is not the page and outlives it: a new build reloads the
	 *  screen and the record goes on playing out of the amplifier, so the page
	 *  has to recognise what is on rather than start it again — and until it
	 *  does, nothing anywhere can see what is playing. */
	resume(tracks: QueueTrack[], from: number, at: number) {
		this.tracks = tracks;
		this.index = Math.max(0, Math.min(from, tracks.length - 1));
		this.position = at;
		this.startAt = 0;
		this.playing = true;
		this.attached = true;
	}

	/** what is on, so the page that comes back knows what the box is doing */
	keep() {
		if (!this.tracks.length) forget(KEPT);
		else keep(KEPT, JSON.stringify({ tracks: this.tracks, index: this.index }));
	}

	kept(): { tracks: QueueTrack[]; index: number } | null {
		try {
			const got = JSON.parse(recall(KEPT) ?? 'null');
			return got?.tracks?.length ? got : null;
		} catch {
			return null;
		}
	}

	jump(index: number) {
		if (index < 0 || index >= this.tracks.length) return;
		this.index = index;
		this.position = 0;
		this.startAt = 0;
		this.playing = true;
		this.keep();
	}

	/** A record played through is not a record left paused on its last song. The
	 *  queue used to stop and keep it, so the bar stood along the bottom of every
	 *  screen for the rest of the evening, showing a record that had finished and
	 *  offering a play key that would put the last song on again.
	 *
	 *  A station is the exception: it has no end, so a stream that stops has
	 *  dropped rather than finished, and clearing it would take away the one key
	 *  that gets it back. */
	next() {
		if (this.hasNext) this.jump(this.index + 1);
		else if (this.current?.live || this.current?.url) this.playing = false;
		else this.clear();
	}

	clear() {
		this.tracks = [];
		this.index = 0;
		this.playing = false;
		this.position = 0;
		this.startAt = 0;
		this.attached = false;
		this.keep();
	}
}

export const queue = new QueueState();
