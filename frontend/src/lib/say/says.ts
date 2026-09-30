// What a thing is called, said once.
//
// A season, an episode, a line of one: every screen that draws them was
// deciding for itself what they say — the ten-foot list, the page on a desk,
// the panel over both. That is how one of them called an ignored season
// "wanted" while the other called it ignored, and how a name could differ
// between two screens of the same player. Nothing is named anywhere else.

import { formatDate, formatNumber, t } from '$lib/i18n';
import { videoStateMark, type Count, type PageTag } from '$lib/opus';
import { aired, episodeLabel, episodeState } from '$lib/say/episode';
import { watched } from '$lib/keep/watched.svelte';
import type { EpisodeEntry, SeasonView, SeriesTree } from '$lib/keep/types';

/** The seasons of a series the house holds, as every list of them reads them. */
export function seasonViews(tree: SeriesTree | null): SeasonView[] {
	return (tree?.seasons ?? []).map((one) => ({
		number: one.number,
		episodes: one.episodes,
		total: one.episodes.length,
		have: one.episodes.filter((e) => e.playable).length,
		followed: one.followed,
		overview: one.overview,
		poster: one.poster
	}));
}

/** A season by name. */
export function seasonName(number: number): string {
	return `${t('sheet.season')} ${formatNumber(number)}`;
}

/** How much of something is here, out of how much there is. */
export function haveOf(have: number, total: number): string {
	return `${formatNumber(have)}/${formatNumber(total)}`;
}

/** What the control beside a season's name is for. Marking is only ever about
    what the house holds — saying you have seen a season nobody has a copy of
    is bookkeeping with nothing on the other end of it. Clearing is about
    whatever is marked, so a mark can always be taken back. */
export function seasonMark(season: SeasonView) {
	const all = season.episodes.map((e) => e.id);
	const here = season.episodes.filter((e) => e.playable).map((e) => e.id);
	const marked = watched.count('episode', all);
	const clearing = here.length ? watched.count('episode', here) === here.length : marked > 0;
	return {
		show: here.length > 0 || marked > 0,
		clearing,
		ids: clearing ? all : here,
		label: clearing ? t('series.unmarkSeason') : t('series.markSeason')
	};
}

/** A season in three numbers: how much of it this profile has seen, how
    much has not been broadcast yet, and how much there is — or, for one nobody
    follows, that nobody follows it. A season that was watched and then let go
    is not a season with something missing from it. */
export function seasonCounts(season: SeasonView): Count[] {
	if (season.followed === false) return [{ icon: 'ignored', n: '', text: t('series.notFollowed') }];
	const ids = season.episodes.map((e) => e.id);
	const seen = watched.count('episode', ids);
	const upcoming = season.episodes.filter((e) => !aired(e)).length;
	return [
		{
			icon: 'check',
			n: formatNumber(seen),
			text: t('series.tally.seen'),
			tone: seen === season.total && season.total > 0 ? 'ok' : 'quiet'
		},
		...(upcoming ? [{ icon: 'clock', n: formatNumber(upcoming), text: t('series.tally.upcoming') }] : []),
		{ icon: 'list', n: formatNumber(season.total), text: t('series.tally.total') }
	];
}

/** The same, as one line — what is read out where there is no room for marks. */
export function seasonLine(season: SeasonView): string {
	return seasonCounts(season)
		.map((one) => (one.n ? `${one.n} ${one.text}` : one.text))
		.join(' · ');
}

/** What stands beside an episode, as a mark: only what is not simply there to
    be watched. The file's resolution and languages are the Library's business,
    and whether this profile has seen it is the line's own check. */
export function episodeTags(season: SeasonView, e: EpisodeEntry): PageTag[] {
	// "wanted" is what the catalogue calls anything it has no file for,
	// whether or not it is looking. A season nobody follows is not being
	// looked for, and every line of it is ignored.
	const state = !e.playable && !aired(e) ? 'upcoming' : !e.playable && season.followed === false ? 'ignored' : e.state;
	const mark = videoStateMark(e.playable && state !== 'waiting_subtitles' ? 'complete' : state);
	if (!mark) return [];
	return [
		{
			...mark,
			text: state === 'ignored' ? t('series.notFollowed') : episodeState(e),
			title: state === 'waiting_subtitles' ? (e.missing_subs ?? []).join(', ').toUpperCase() : ''
		}
	];
}

/** An episode by name: its own title where it has one, and the number where it
    has not — which is also how it is announced while it plays. */
export function episodeName(seasonNumber: number, e: EpisodeEntry): string {
	return e.title || episodeLabel(seasonNumber, e);
}

/** What a round of the guessing game asks, and what the answer turned out to
    be. The screen draws it; what it says is decided here, like everything else
    a screen says. */
export function askedOf(kind: 'who' | 'where' | 'when'): string {
	return kind === 'who' ? t('guess.who') : kind === 'where' ? t('guess.where') : t('guess.when');
}

/** The whole truth about a photograph, once it has been guessed at: where it
    was taken, when, and who is in it — not only the fact that was asked about.
    The picture is the point of the game, and half of what it is would be a poor
    reward. */
export function photoSays(facts: {
	taken_at: string;
	place: string | null;
	people: { name: string }[];
}): string {
	const when = new Date(facts.taken_at);
	const years = new Date().getFullYear() - when.getFullYear();
	const said = [formatDate(facts.taken_at)];
	if (facts.place) said.unshift(facts.place);
	if (years >= 1) said.push(t('photos.yearsAgo', { n: formatNumber(years) }));
	if (facts.people.length) said.push(namesOf(facts.people.map((p) => p.name)));
	return said.join(' · ');
}

/** Who a photograph or a day is about, in the way a person would say it: two
    names joined, three listed and the last joined, and after that the rest
    counted rather than recited — "Eva, Kata and Filip and 21 more" is a
    sentence with two ands in it. */
export function namesOf(all: string[]): string {
	const names = all.slice(0, 3);
	const more = all.length - names.length;
	if (!names.length) return '';
	if (more > 0) return `${names.join(', ')} ${t('photos.andMore', { n: formatNumber(more) })}`;
	return names.length === 1
		? names[0]
		: `${names.slice(0, -1).join(', ')} ${t('common.and')} ${names[names.length - 1]}`;
}
