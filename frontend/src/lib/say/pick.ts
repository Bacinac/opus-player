// Where a card leads. Everything else opens the panel over the screen it was
// found on, but a series the house holds is a page: seasons, episodes, sizes,
// what is still missing. Told here once so the shelf, the home rows and Explore
// cannot disagree about it.

import { goto } from '$app/navigation';
import type { Card } from '$lib/keep/types';

/** True when the card was taken somewhere, and the caller should not open the
    panel for it. */
export function opened(card: Card): boolean {
	if (card.kind !== 'series' || card.owned === false) return false;
	goto(`/series/${card.id}`);
	return true;
}

/** A film or an episode on the row of what is being gone on with is put on,
    not read about: the panel it would open says what its cover already says. */
export function playsAtOnce(row: { key: string }, card: Card): boolean {
	// `watching` on a section's shelf, `continue` on the desk's home
	return (row.key === 'watching' || row.key === 'continue') && (card.kind === 'episode' || card.kind === 'movie');
}

/** A record is opened where records are: on its artist's page, already open
    at it. */
export function atItsArtist(card: Card): Card {
	if (card.kind !== 'release' || !card.artist_id) return card;
	return {
		kind: 'artist',
		id: card.artist_id,
		title: card.artist ?? '',
		image: null,
		backdrop: null,
		state: null,
		overview: '',
		round: true,
		person: true,
		release_id: card.id
	};
}
