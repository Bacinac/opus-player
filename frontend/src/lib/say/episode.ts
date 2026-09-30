// How an episode reads. The panel, the series page and whatever plays it all
// name and describe the same episode, so they say it the same way or the product
// speaks with two voices about one thing.

import { t } from '$lib/i18n';
import { episodeCode } from '$lib/opus';
import type { Card, EpisodeEntry } from '$lib/keep/types';

const STATE_KEY = {
	complete: 'state.complete',
	waiting_subtitles: 'state.waiting_subtitles',
	downloading: 'state.downloading',
	ignored: 'state.ignored',
	wanted: 'state.wanted'
} as const;

export function stateOf(episode: EpisodeEntry) {
	return STATE_KEY[episode.state as keyof typeof STATE_KEY] ?? 'state.wanted';
}

/** An episode broadcast is one the library can look for; one that has not been
    is not being looked for by anybody, and a row saying otherwise promises a
    wait it cannot end. */
export function aired(episode: EpisodeEntry): boolean {
	return !episode.air_date || episode.air_date <= new Date().toISOString().slice(0, 10);
}

export function episodeLabel(seasonNumber: number, episode: Pick<EpisodeEntry, 'number' | 'title'>): string {
	const code = episodeCode(seasonNumber, episode.number);
	return episode.title ? `${code} · ${episode.title}` : code;
}

/** A card as the backend sends it, with the line under an episode said here. */
export function spoken(card: Card): Card {
	if (card.kind !== 'episode' || card.season_number === undefined) return card;
	return {
		...card,
		subtitle: episodeLabel(card.season_number, {
			number: card.number ?? 0,
			title: card.episode_title ?? ''
		})
	};
}

/** What the state tag says: the state itself, or — for an episode still to be
    broadcast — that it is a date away rather than a search away. */
export function episodeState(episode: EpisodeEntry): string {
	return aired(episode) ? t(stateOf(episode)) : t('state.upcoming');
}
