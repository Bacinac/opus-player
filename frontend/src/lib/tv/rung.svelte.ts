// The last rung of the ladder on a television, the one under everything that
// stands over anything. A remote climbs; it does not go back through history.
// So BACK here means "take away what is on top": a page returns to the shelf
// above it, the shelf to the menu, and only the menu leaves.

import { goto } from '$app/navigation';
import { pageOf } from '$lib/say/ways';

const here = (url: URL) => url.pathname + url.search;
const depth = (url: URL) => url.pathname.split('/').filter(Boolean).length;
const inMenu = () => Boolean(document.activeElement?.closest('nav.rail'));

class Rung {
	/** Nothing left to climb: what back can still mean is offered instead. */
	leaving = $state(false);
	#askedFrom = new Map<string, string>();

	/** A question — everything one actor was in — is asked from a page, and the
	 *  rung above it is that page, not the section it happens to be answered on. */
	went(from: URL, to: URL) {
		if (here(from) === here(to) || pageOf(to.searchParams) !== 'discover') return;
		if (!this.#askedFrom.has(here(to))) this.#askedFrom.set(here(to), here(from));
	}

	asked(url: URL): boolean {
		return this.#askedFrom.has(here(url));
	}

	/** One rung up from `url`; true, because at the bottom it offers the way out. */
	climb(url: URL): boolean {
		if (this.leaving) {
			this.leaving = false;
			return true;
		}
		const asked = this.#askedFrom.get(here(url));
		if (asked) {
			this.#askedFrom.delete(here(url));
			goto(asked, { replaceState: true });
			return true;
		}
		// a page goes to its section's shelf, and where it lands is where it was
		// left from
		if (depth(url) > 1) {
			goto(`/${url.pathname.split('/').filter(Boolean)[0]}`, { replaceState: true });
			return true;
		}
		// from a section's page the menu is the rung above it, and only from the
		// menu is the next one out
		const marked =
			document.querySelector<HTMLElement>('nav.rail a.here') ??
			document.querySelector<HTMLElement>('nav.rail a.in');
		if (!inMenu() && marked) {
			marked.focus();
			return true;
		}
		this.leaving = true;
		return true;
	}

	/** Whether a press would climb rather than open the way out. A section IS a
	 *  first level: the menu is how you cross between them, and only something
	 *  deeper has a shelf above it to return to. */
	holds(url: URL): boolean {
		return this.leaving || !inMenu() || depth(url) > 1 || this.asked(url);
	}
}

export const rung = new Rung();
