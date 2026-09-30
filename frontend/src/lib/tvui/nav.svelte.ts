/* Where you are on this television, and where the remote was when you left.
 *
 * Two things, and they are the same thing.
 *
 * THE LEVEL is derived from the path and from nothing else. One segment or none
 * is the menu screen; anything deeper is a page that has taken the screen. No
 * flag, no store, no component announcing which it is — which is why the rail's
 * visibility, the page's width, what LEFT means at the left edge, and what BACK
 * does are one rule rather than four that have to be kept in agreement.
 *
 * THE PERCH is where the ring actually was, remembered per path. It replaces
 * chasing selectors after the fact — reconstructing "the card I opened" from a
 * string, hoping the page has drawn it yet. Every focus counts, including the
 * ones a component causes itself, so the memory cannot drift from what happened.
 */

import { page } from '$app/state';
import { showing } from './reach';

const perches = new Map<string, string>();

/* How many second-level views are open.
 *
 * The level was read off the depth of the path alone. That is true for the one
 * screen that has a path of its own and wrong for every other: a film, an
 * artist, a person, a place and a search result all TAKE THE SCREEN, and all of
 * them are component state at a depth of one. So the menu went on being drawn
 * beside them and they went on being laid out inside the column it keeps.
 *
 * The level is a fact about what is on the screen, not about the address. A view
 * that takes it says so while it is mounted; when it earns a path of its own it
 * stops saying so and the depth answers instead. */
let open = $state(0);

function depth(path: string): number {
	return path.split('/').filter(Boolean).length;
}

class Nav {
	/** 1 = the menu screen, 2 = a page. Read, never written. */
	get level(): 1 | 2 {
		return depth(page.url.pathname) > 1 || open > 0 ? 2 : 1;
	}

	/** Said by a view for as long as it is taking the screen:
	 *      $effect(() => nav.takes());
	 *  The returned function gives it back, so a view cannot forget to. */
	takes(): () => void {
		// After the flush that mounted the caller, never inside it. Taking the
		// screen flips the frame — the menu unmounts, the column is released,
		// every width on the page moves — and doing that synchronously inside
		// the mounting child's own effect re-entered the same flush until Svelte
		// gave up: effect_update_depth_exceeded, the whole instance wedged, a
		// person opened onto a frozen empty shelf with a dead back.
		let given = false;
		// only what was counted is given back: a view gone before its count
		// arrived would otherwise take away another view's
		let counted = false;
		queueMicrotask(() => {
			if (given) return;
			open += 1;
			counted = true;
		});
		return () => {
			if (given) return;
			given = true;
			queueMicrotask(() => {
				if (counted) open -= 1;
			});
		};
	}

	/** Which section this belongs to, at either level: /series/12/s/2 is Series. */
	get section(): string {
		const first = page.url.pathname.split('/').filter(Boolean)[0];
		return first ? `/${first}` : '/';
	}

	/** Hand the ring back to the tile something was opened from.
	 *
	 *  The remote has `land`, which waits for the page and argues with whatever
	 *  else wants focus. A pointer needs neither: the shelf is already drawn
	 *  when the thing over it closes, and nothing else is asking. What it does
	 *  need is the scroll — coming back to the top of a shelf of two hundred
	 *  loses the one thing the shelf was showing you, which is where you were. */
	returnTo(perch: string | null) {
		if (!perch) return;
		queueMicrotask(() => {
			const tile = document.querySelector<HTMLElement>(`[data-perch="${CSS.escape(perch)}"]`);
			if (!tile) return;
			tile.scrollIntoView({ block: 'center' });
			// says the mark is ours rather than a keyboard's, which is what lets
			// the ring be drawn at all; gone the moment the ring moves on
			tile.dataset.returned = '';
			tile.addEventListener('blur', () => delete tile.dataset.returned, { once: true });
			tile.focus({ preventScroll: true });
		});
	}

	/** Note where the ring is. Called from one focusin listener, so a component
	 *  that moves focus itself is recorded exactly like a person pressing an
	 *  arrow — the two were indistinguishable to anybody watching anyway. */
	remember(el: Element | null) {
		const at = el instanceof HTMLElement ? el.dataset.perch : undefined;
		if (at) perches.set(page.url.pathname, at);
	}

	/** What the ring was on last time this path was open, if anything. */
	perch(path = page.url.pathname): string | undefined {
		return perches.get(path);
	}

	/** Put the remote back where it was, or on the first thing that will do.
	 *
	 *  Kept trying for a moment rather than asked once: a page arrives and fills
	 *  in, and the row a person left by is drawn after the frame that carries it.
	 *  Anything already holding the remote wins — a panel that opened while the
	 *  page was arriving asked for it on purpose, and taking it back would be
	 *  this function fighting a component that knows better. */
	/** `fallback` may be several selectors, tried IN ORDER — which one
	 *  `querySelector` would answer with is document order, and document order
	 *  puts the head of a page before the list it is about: the ring landed on
	 *  the name of whoever directed a series rather than on its first season. */
	land(fallback: string | string[], within = 'main'): () => void {
		const wanted = Array.isArray(fallback) ? fallback : [fallback];
		const want = this.perch();
		let tries = 0;
		const timer = setInterval(() => {
			tries += 1;
			const active = document.activeElement as HTMLElement | null;
			// Anything already holding the remote wins. The menu counts: walking it
			// changes the page under it, and a page arriving must not reach up and
			// take the ring out of the list you are still walking.
			if (
				active &&
				active !== document.body &&
				(active.closest('[data-holds-remote]') || active.closest('nav.rail'))
			) {
				clearInterval(timer);
				return;
			}
			const root = document.querySelector(within) ?? document;
			const back = want
				? root.querySelector<HTMLElement>(`[data-perch="${CSS.escape(want)}"]`)
				: null;
			const any = back ?? wanted.reduce<HTMLElement | null>((found, one) => found ?? showing(one, root), null);
			if (any) {
				any.focus({ preventScroll: true });
				// only when it actually took: a page still being built can lose the
				// ring again a frame later, and stopping here left it on the
				// document with every arrow dead
				if (document.activeElement === any) {
					clearInterval(timer);
					return;
				}
			}
			if (tries > 40) clearInterval(timer);
		}, 50);
		return () => clearInterval(timer);
	}
}

export const nav = new Nav();
