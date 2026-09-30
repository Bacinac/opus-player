// Asking for a thing, and saying what came of it. The same sentence from
// Explore, where nothing is held yet, and from a shelf, where the series is held
// and its episodes are not — the library takes both as the same request.

import { request, toasts } from '$lib/kit';
import { t } from '$lib/i18n';
import { aired, episodeLabel } from '$lib/say/episode';
import { formatDate } from '$lib/i18n';
import type { Card, EpisodeEntry } from '$lib/keep/types';

/** One record of an artist the house follows. What it costs is one record,
 *  and the queue is where it can be taken back, so nothing asks first. */
export async function wantRecord(id: number): Promise<boolean> {
	return !!(await request(`/api/explore/want/release/${id}`, { method: 'POST' }));
}

/** `seasons` empty means all of them; `only` says the named ones are the whole
    of what is wanted, which is a sentence to be spoken when taking a series on
    and not when fetching a season of one already held. */
export async function want(card: Card, seasons: number[] = [], only = false) {
	// A catalogue put this in front of us and knows the artist by its own id,
	// which the library does not. Asking for them by name is what the two have in common.
	if (card.kind === 'music') {
		const got = await request<{ added: boolean; name: string }>('/api/explore/want/music', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ artist: card.artist ?? '', album: card.album ?? card.title })
		});
		if (!got) return;
		toasts.success(
			got.added ? t('explore.wanted', { title: got.name }) : t('explore.already')
		);
		return;
	}

	const answer = await request<{
		added: boolean;
		queued: number;
		title?: string;
		found?: boolean;
		coming?: boolean;
	}>(
		'/api/explore/want',
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				kind: card.kind === 'series' ? 'series' : 'movie',
				tmdb_id: card.tmdb_id,
				seasons,
				only
			})
		}
	);
	if (!answer) return;
	const title = answer.title ?? card.title;
	if (answer.coming) toasts.info(t('series.onItsWay', { title }));
	else if (answer.found === false) toasts.info(t('series.nothing', { title }));
	else
		toasts.success(
			answer.queued
				? t('explore.queued', { title, n: answer.queued })
				: answer.added || answer.found
					? t('explore.wanted', { title })
					: t('explore.already')
		);
}

/** One episode, by name — the line that is not here yet. What the library
    declines to find it says so, and the screen says so back rather than leaving
    somebody pressing again. An episode that has not been broadcast is not being
    looked for by anybody, so it is answered with the date instead. */
export async function askEpisode(episode: EpisodeEntry, seasonNumber = 0): Promise<boolean> {
	const name = episode.title || episodeLabel(seasonNumber, episode);
	if (!aired(episode)) {
		toasts.info(t('series.notYet', { date: formatDate(episode.air_date ?? '') }));
		return false;
	}
	const answer = await request<{ found: boolean; already: boolean; release?: string }>(
		`/api/explore/want/episode/${episode.id}`,
		{ method: 'POST' }
	);
	if (!answer) return false;
	if (answer.already) toasts.info(t('series.onItsWay', { title: name }));
	else if (answer.found) toasts.success(t('series.asked', { title: name }));
	else toasts.info(t('series.nothing', { title: name }));
	return Boolean(answer.found);
}
