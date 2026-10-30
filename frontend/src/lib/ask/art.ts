// A cover at the size it is about to be drawn.
//
// Every picture in the catalogue is the Library's, at /api/pictures/{id}, and
// the player answers on the same address; the screen only says how wide it
// draws it. What the player serves itself, the photographs, is its own address
// already. Anything else is somebody else's server, which no screen asks.

const PICTURE = /^\/api\/pictures\/\d+$/;

export function art(url: string | null | undefined, edge: number): string {
	if (!url) return '';
	if (PICTURE.test(url)) return `${url}?w=${edge}`;
	return url.startsWith('/') ? url : '';
}

/** A picture as something outside this page fetches it — the television's own
 *  engine, which has no origin to resolve an address against. */
export function artAbroad(url: string | null | undefined, edge: number): string {
	const here = art(url, edge);
	return here ? new URL(here, location.origin).href : '';
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
