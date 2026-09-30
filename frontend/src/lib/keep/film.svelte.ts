// The film this box is playing through its own engine, while there is one.
//
// A television is told what to do from the rest of the house — the phone, the
// house's automation, the remote's media keys — and those orders arrive where
// the music is kept. A film has
// its own screen and its own controls; this is how an order reaches them rather
// than the queue, and how the house hears what the film is doing.

import type { Card } from '$lib/keep/types';

export type FilmOnTv = {
	kind: string;
	id: number;
	title: string;
	subtitle: string;
	cover: string | null;
	position: () => number;
	duration: () => number;
	seek: (to: number) => void;
	playing: () => boolean;
	toggle: () => void;
	step: (by: 1 | -1) => void;
	/** on to the next episode, where there is one */
	episode: () => void;
	stop: () => void;
};

class Film {
	// raw: a closing screen clears this only if it is still its own, and a proxy is never `===` its target
	current = $state.raw<FilmOnTv | null>(null);
	/** a film somebody elsewhere in the house asked this television to play */
	asked = $state<Card | null>(null);
	/** how many film screens are open, counted outside the reactive graph: the
	    frame asks it only when deciding whether a new build may reload now */
	screens = 0;
	/** where the screen that sent the film had got to: it plays on from there,
	    not from wherever this box's own profile last left it */
	private from: { kind: string; id: number; at: number } | null = null;
	/** the mark a film sent from somebody's phone comes with: while it plays, and
	    the episodes after it, where it got to is theirs, not this box's profile's */
	private lent: { kind: string; id: number; token: string } | null = null;

	ask(card: Card, at?: number, sent?: string) {
		this.current?.stop();
		this.from = at ? { kind: card.kind, id: card.id, at } : null;
		this.carryOn(card, sent ?? null);
	}

	/** the next episode, played on for whoever the one before was played for */
	carryOn(card: Card, lent: string | null) {
		this.lent = lent ? { kind: card.kind, id: card.id, token: lent } : null;
		this.asked = card;
	}

	close() {
		this.asked = null;
		this.lent = null;
	}

	lentFor(card: Card): string | null {
		const lent = this.lent;
		return lent && lent.kind === card.kind && lent.id === card.id ? lent.token : null;
	}

	/** the place a film was sent to, taken once, by that film alone */
	sentAt(card: Card): number | null {
		const from = this.from;
		if (!from || from.kind !== card.kind || from.id !== card.id) return null;
		this.from = null;
		return from.at;
	}
}

export const film = new Film();
