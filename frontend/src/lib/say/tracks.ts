import { formatNumber, t } from '$lib/i18n';
import type { PlanSubtitle } from '$lib/keep/types';

export function soundName(track: { lang: string; channels: number | null; codec: string }): string {
	return [
		track.lang.toUpperCase(),
		track.channels ? t('play.channels', { n: formatNumber(track.channels) }) : '',
		track.codec
	]
		.filter(Boolean)
		.join(' · ');
}

/** The engine normalises a language into codes nobody reads — hbs-hrv for the
 *  Croatian file the catalogue went and found — and the last part of one is the
 *  language itself. */
export function languageOf(code: string): string {
	const last = code.split('-').pop() ?? '';
	return /^[a-z]{2,3}$/i.test(last) ? last : '';
}

export function subtitleName(sub: { lang: string; label?: string; forced?: boolean; number: number }): string {
	const parts = [sub.lang ? sub.lang.toUpperCase() : '', sub.label ?? ''].filter(Boolean);
	const name = parts.join(' · ') || t('play.subtitleTrack', { n: formatNumber(sub.number) });
	return sub.forced ? `${name} · ${t('play.forced')}` : name;
}

/** The tracks in the order worth offering: the languages this house asks for
 *  first, then the rest. Forty-eight of them in file order is a list nobody
 *  reads. */
const PREFERRED = ['hr', 'en'];

export function offeredSubtitles(subs: PlanSubtitle[]): PlanSubtitle[] {
	const rank = (lang: string) => {
		const i = PREFERRED.indexOf(lang);
		return i === -1 ? PREFERRED.length : i;
	};
	return [...subs].sort(
		(a, b) =>
			rank(a.lang) - rank(b.lang) || a.lang.localeCompare(b.lang) || Number(a.forced) - Number(b.forced)
	);
}
