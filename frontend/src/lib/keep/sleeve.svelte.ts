// Whether the record is on the screen or along the bottom of it.
//
// Putting a record on opens it: what a person did was choose an album, and the
// answer to that is the album — its sleeve, its songs, its words — not a strip
// of furniture under a page they had already stopped looking at. Closing it
// leaves the music playing; the bar is the same record, made small.

class SleeveState {
	open = $state(false);
	/** the record a page is already showing, if a page is showing one. Putting on
	    a record you are looking at must not open a second copy of it over the
	    first: it is one screen, and pressing a song on it is not going anywhere. */
	onScreen = $state<number | null>(null);

	show() {
		this.open = true;
	}

	hide() {
		this.open = false;
	}
}

export const sleeve = new SleeveState();
