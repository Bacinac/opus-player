// A cover at the size it is about to be drawn.
//
// Not the catalogue's own address. What it stores is where the picture came
// from — an artist's face is a thousand pixels square on Deezer's CDN, which is
// a hundred and thirty kilobytes for a face a shelf draws at three hundred, and
// that CDN dates its answers in the past so the browser fetches the lot again
// every time the shelf is opened. The player keeps them instead, sized, on the
// same network as the screen.

export function art(url: string | null | undefined, edge: number): string {
	if (!url) return '';
	// What this player serves itself is not proxied. The proxy exists to size and
	// keep pictures that live on somebody else's CDN, and it refuses any host
	// that is not one of those — which is how the photographs' own section had no
	// ground behind it at all: every request for one answered 400.
	if (url.startsWith('/')) return url;
	return `/api/art?w=${edge}&u=${encodeURIComponent(url)}`;
}

/** The picture to lie behind a screen that is about one thing: its own wide
 *  artwork if the catalogue has any, and otherwise its poster, which is thrown
 *  far enough out of focus to be a colour rather than a picture.
 *
 *  A station has neither. Its mark is a logo on white, and a logo on white
 *  blurred across the screen is a white screen. */
export function ground(card: { kind?: string; backdrop?: string | null; image?: string | null } | null | undefined): string | null {
	if (!card || card.kind === 'station') return null;
	if (card.backdrop) return art(card.backdrop, 780);
	return card.image ? art(card.image, 320) : null;
}
