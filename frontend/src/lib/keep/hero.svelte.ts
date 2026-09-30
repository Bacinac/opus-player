// What has focus, for the panel at the top that describes it.
//
// A card announces itself the moment it is focused and the panel reads it a
// moment later. The delay is the whole point: a held-down arrow flies through
// twenty cards on the way to the one you want, and describing each of them in
// turn is a strobe. Nothing is ever cleared on the way — the last thing
// described stays until the next one settles, so the panel never blinks empty.

import type { Card } from '$lib/keep/types';

const SETTLE_MS = 180;

let described = $state<Card | null>(null);
// what was chosen, which outranks what has focus: once a thing is open the
// panel is about that thing, and the focus has moved inside it anyway
let chosen = $state<Card | null>(null);
// What lies BEHIND the page, which is not the same question as what the panel
// is describing. The panel is cleared the moment the remote leaves a poster —
// for the menu, for the head, for a page nobody has pointed at yet — and the
// picture must not go with it. A ten-foot screen whose ground turns black while
// the sections are being read has no ground: on the home screen the remote
// arrives IN the menu, so that was every time.
let lastSeen = $state<Card | null>(null);
let timer: ReturnType<typeof setTimeout> | undefined;
// How many panels are on screen. One, except for the moment a page changes:
// the arriving page builds its panel before the leaving page tears its own
// down, and the two orders are not ours to choose.
let panels = 0;
// A page hands the remote to its first poster on the way in. Nobody asked for
// that one, so the panel goes on saying what the screen is until somebody
// actually moves — arriving at a shelf and being told about its first item is
// the summary of the shelf never being seen at all.
let unasked = false;

function silence() {
	clearTimeout(timer);
	described = null;
	chosen = null;
}

export const hero = {
	get card() {
		return chosen ?? described;
	},
	get open() {
		return chosen !== null;
	},
	/** The picture behind the whole page: what the remote was last on, which
	 *  outlives the panel's description of it and survives a page change rather
	 *  than flashing black until the next poster settles. */
	get behind() {
		return chosen ?? described ?? lastSeen;
	},
	take(card: Card) {
		clearTimeout(timer);
		chosen = card;
	},
	release() {
		chosen = null;
	},
	show(card: Card) {
		// the ground follows the remote even where the panel is told not to:
		// being PUT somewhere is still the screen being about that thing, even
		// when nobody asked to be told about it
		lastSeen = card;
		if (unasked) {
			unasked = false;
			return;
		}
		clearTimeout(timer);
		timer = setTimeout(() => (described = card), SETTLE_MS);
	},
	/** The remote has left the shelf for the panel itself — asking where else to
	 *  look is not looking at anything, so the panel goes back to being about
	 *  the shelf rather than about the last poster passed. */
	forget() {
		clearTimeout(timer);
		described = null;
	},
	/** about to put the remote somewhere nobody asked for it to be */
	hush() {
		unasked = true;
	},
	/** and somebody has now asked */
	wake() {
		unasked = false;
	},
	// a page arrives with nothing said about it yet, whatever the last one said
	arrive() {
		panels += 1;
		silence();
	},
	// and a page leaves quietly if another has already taken its place: a panel
	// being torn down must not wipe the words of the one that replaced it
	leave() {
		panels -= 1;
		if (panels <= 0) silence();
	}
};
