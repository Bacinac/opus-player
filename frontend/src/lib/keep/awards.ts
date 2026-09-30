// Which winners an award wall shows, and the years each stands under.

import type { Stances } from './streaming';
import type { Card } from './types';

/** The titles that won any award asked for alone (every winner when none is),
 *  less those that won an award left out, the most recent win first. Each
 *  carries the years it won what is being looked at. */
export function winners(cards: Card[], stances: Stances): Card[] {
	const years = (card: Card) =>
		[
			...new Set(
				Object.entries(card.won ?? {})
					.filter(([body]) => !stances.only.length || stances.only.includes(body))
					.flatMap(([, won]) => won)
			)
		].sort();
	return cards
		.filter((card) => !Object.keys(card.won ?? {}).some((body) => stances.without.includes(body)))
		.map((card) => ({ card, won: years(card) }))
		.filter((w) => w.won.length)
		.sort((a, b) => Math.max(...b.won) - Math.max(...a.won) || a.card.title.localeCompare(b.card.title))
		.map((w) => ({ ...w.card, subtitle: w.won.join(', ') }));
}
