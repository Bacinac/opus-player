// Which shelf the remote is merely passing.
//
// Standing on a section in the menu is asking about that section without
// opening it, so the panel answers for it — how much is on it and the ways into
// it — while the shelf on the screen is still whatever was there before.
// Landing on anything else is the question being dropped.

import { settle } from '$lib/kit';

class PreviewState {
	section = $state<string | null>(null);
	/** the picture a section stands in front of: its shelf's first card, noted
	 *  by the shelf when it loads, so passing the section in the menu can put
	 *  that section's own ground behind the screen without a fetch */
	fronts = $state<Record<string, import('./types').Card>>({});
	/** the menu was pressed, not merely passed: the screen it opens should hand
	 *  the remote to the first way in rather than to a poster */
	landing = $state(false);

	show(section: string) {
		this.section = section;
	}

	front(section: string, card: import('./types').Card | undefined) {
		// settle, not a hand-rolled guard: writing state from inside an effect's
		// call chain is the shape that wedged this app twice in one day, and the
		// shared function is where that lesson is kept
		if (card) settle(this.fronts, section, card);
	}

	clear() {
		this.section = null;
	}

	press(section: string) {
		this.section = section;
		this.landing = true;
	}

	landed() {
		const was = this.landing;
		this.landing = false;
		return was;
	}
}

export const preview = new PreviewState();
