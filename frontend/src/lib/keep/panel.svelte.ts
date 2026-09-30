// What is standing over a shelf, and the way back down.
//
// A shelf opens one thing at a time, and that thing can name others — the band
// somebody was in, the people who were in it. Standing on one of those is going
// one further in rather than sideways, so the way back is a trail and not a
// door: otherwise back walks out of a band AND the member it was opened from in
// a single press, because nothing remembers there was a first one.
//
// Made per screen rather than shared. Two shelves holding one trail between
// them would hand the records' trail to the films.

import type { Card } from './types';
import { hero } from './hero.svelte';
import { nav } from '$lib/tvui/nav.svelte';
import { surface } from './surface.svelte';

export function panel() {
	let card = $state<Card | null>(null);
	// where the ring goes when the last of it closes, and what it stood on
	// before. Neither is reactive: both are written when something opens and
	// read when it closes, and a state read inside the effect that writes it is
	// the loop that turns the page white.
	let from: string | null = null;
	let trail: Card[] = [];

	return {
		get card() {
			return card;
		},
		/** opened off the shelf itself */
		open(next: Card) {
			hero.take(next);
			from = `${next.kind}:${next.id}`;
			trail = [];
			card = next;
		},
		/** opened off what is already open */
		stand(next: Card) {
			if (card) trail.push(card);
			hero.take(next);
			card = next;
		},
		/** Returns true when a rung was taken and the shelf is still covered. */
		close(): boolean {
			hero.release();
			const before = trail.pop();
			if (before) {
				hero.take(before);
				card = before;
				return true;
			}
			card = null;
			// a remote has its own way of landing; this is the pointer's
			if (!surface.isTv) nav.returnTo(from);
			from = null;
			return false;
		}
	};
}
