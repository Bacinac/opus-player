// How a subtitle looks, kept per device.
//
// Per device rather than per person, and deliberately: the same viewer wants a
// different size on a laptop at arm's length than on the television across the
// room, and the device is the thing that differs. Language belongs to the
// person and is stored once for the whole of OPUS; this is the other kind.
//
// Size is a share of the PICTURE's height, not the screen's and not the video
// element's. That is what makes one default right everywhere: the same share
// subtends roughly the same angle whether the picture is a window on a laptop
// or a wall seen from a sofa. Reading it off the element instead is what left
// the browser drawing sixty-nine-pixel text into the black bar under a film.

import { keep, recall } from '$lib/kit';

export type CaptionSize = 'small' | 'medium' | 'large' | 'huge';
export type CaptionPlace = 'picture' | 'below';
export type CaptionBackdrop = 'none' | 'shadow' | 'box';

export const CAPTION_SIZES: CaptionSize[] = ['small', 'medium', 'large', 'huge'];
export const CAPTION_PLACES: CaptionPlace[] = ['picture', 'below'];
export const CAPTION_BACKDROPS: CaptionBackdrop[] = ['none', 'shadow', 'box'];

/** Share of the picture's height one line of subtitle occupies. */
const SHARE: Record<CaptionSize, number> = {
	small: 0.028,
	medium: 0.036,
	large: 0.045,
	huge: 0.056
};

const KEY = 'opus.player.captions';

type Kept = { size: CaptionSize; place: CaptionPlace; backdrop: CaptionBackdrop };

class Captions {
	size = $state<CaptionSize>('medium');
	// over the picture by default: a film with no bar to sit in is the ordinary
	// case, and text that moves depending on the aspect ratio reads as a fault
	place = $state<CaptionPlace>('picture');
	backdrop = $state<CaptionBackdrop>('shadow');

	init() {
		let kept: Partial<Kept> = {};
		try {
			kept = JSON.parse(recall(KEY) ?? '{}');
		} catch {
			// a shape from before: the defaults stand
		}
		if (kept.size && CAPTION_SIZES.includes(kept.size)) this.size = kept.size;
		if (kept.place && CAPTION_PLACES.includes(kept.place)) this.place = kept.place;
		if (kept.backdrop && CAPTION_BACKDROPS.includes(kept.backdrop)) this.backdrop = kept.backdrop;
	}

	/** How tall one line is, given the height of the picture it sits on. */
	lineHeight(pictureHeight: number): number {
		return Math.round(pictureHeight * SHARE[this.size]);
	}

	set(next: Partial<Kept>) {
		if (next.size) this.size = next.size;
		if (next.place) this.place = next.place;
		if (next.backdrop) this.backdrop = next.backdrop;
		keep(KEY, JSON.stringify({ size: this.size, place: this.place, backdrop: this.backdrop }));
	}
}

export const captions = new Captions();
