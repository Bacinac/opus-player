// Which subscription services a wall is narrowed to, and which it leaves out.

import { art } from '$lib/ask/art';
import type { Option } from '$lib/tvui/Choose.svelte';
import type { Card, Service } from './types';

export const STANCES = 'opus.streaming.services';

export type Stances = { only: string[]; without: string[] };

const keys = (said: unknown): string[] =>
	Array.isArray(said) ? said.filter((key): key is string => typeof key === 'string') : [];

export function readStances(stored: string | null): Stances {
	try {
		const said = JSON.parse(stored ?? '');
		return { only: keys(said?.only), without: keys(said?.without) };
	} catch {
		return { only: [], without: [] };
	}
}

export function writtenStances(stances: Stances): string | null {
	return stances.only.length || stances.without.length ? JSON.stringify(stances) : null;
}

const streamed = (card: Card): Service[] => (Array.isArray(card.streaming) ? card.streaming : []);

/** The services a wall's titles can be watched on, the house's own first and
 *  then by how many titles each carries. */
export function servicesOf(cards: Card[]): Option[] {
	const seen = new Map<number, { service: Service; titles: number }>();
	for (const card of cards)
		for (const service of streamed(card)) {
			const known = seen.get(service.id);
			if (known) known.titles += 1;
			else seen.set(service.id, { service, titles: 1 });
		}
	return [...seen.values()]
		.sort(
			(a, b) =>
				Number(b.service.ours) - Number(a.service.ours) ||
				b.titles - a.titles ||
				a.service.name.localeCompare(b.service.name)
		)
		.map(({ service }) => ({
			key: String(service.id),
			label: service.name,
			image: service.logo ? art(service.logo, 160) : undefined
		}));
}

/** What stays on the wall: the titles on any service asked for alone (all of
 *  them when none is), less the titles on any service left out. A stance on a
 *  service this wall does not offer says nothing about it, and a title whose
 *  services are not known is never narrowed to and never left out. */
export function sift(cards: Card[], stances: Stances, offered: Option[]): Card[] {
	const here = (key: string) => offered.some((option) => option.key === key);
	const only = stances.only.filter(here);
	const without = stances.without.filter(here);
	const on = (card: Card, among: string[]) =>
		streamed(card).some((service) => among.includes(String(service.id)));
	return cards.filter(
		(card) => (!only.length || on(card, only)) && !(without.length && on(card, without))
	);
}
