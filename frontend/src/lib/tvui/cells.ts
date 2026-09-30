/* How wide one of each kind of thing wants to be, said once.
 *
 * None of these numbers is invented: each is what some screen already drew,
 * written down so the others stop drawing it differently. Before this a face
 * was 72px in Discover and 110 in the photographs; a poster wall declared a
 * COUNT, so the same poster was 120 beside the menu and 163 without it.
 *
 * A wall takes a token; only the count may differ between two screens, because
 * that is what a wider screen means. */

export type Cell = { cell: number; gap: number; rowGap?: number };

/** a film, a series, a record — six beside the menu, which the owner measured
 *  by eye from the sofa; the file behind a poster is 106px wide, so the cell
 *  sits under it and never asks for an upscale */
export const POSTER: Cell = { cell: 96, gap: 16, rowGap: 26 };

/** the desk's poster, unchanged from what the desk drew */
export const DESK_POSTER: Cell = { cell: 136, gap: 14, rowGap: 19 };
export const MOBILE_POSTER: Cell = { cell: 109, gap: 14, rowGap: 19 };

/** a record on its own artist's page, where the sleeve IS the thing being
 *  chosen rather than one of six in a shelf beside the menu */
export const SLEEVE: Cell = { cell: 144, gap: 20 };

/** a person's round portrait — one size, where it was three */
export const FACE: Cell = { cell: 110, gap: 16 };
export const DESK_FACE: Cell = { cell: 140, gap: 14 };

/** a named place in a list — 15rem, picked against real Croatian place names */
export const NAME: Cell = { cell: 240, gap: 6 };

/** a wall of photographs is gutters, not air — the vault's own values */
export const MOSAIC: Cell = { cell: 120, gap: 3 };

/** One year of a day: a picture with its caption under it. Ten feet away it was
 *  stated at the desk's width and the room beside the menu fits two of those —
 *  photographs half the screen wide, on a surface where a film is a sixth of it,
 *  and they are the same kind of thing: something to point at. */
export const YEAR: Cell = { cell: 150, gap: 14 };
/** wide enough for "twenty-one years ago" and a row of names on one line */
export const DESK_YEAR: Cell = { cell: 224, gap: 14 };
