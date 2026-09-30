// What this copy of a thing is, one fact at a time, and who made it. Read on
// the screen a person opens before deciding: they ask what it is, then whether
// this is the good copy of it, and the billing after that.

import { formatBytes } from '$lib/i18n';
import type { About } from '$lib/keep/types';
import { sectionOf } from '$lib/say/ways';

/** Two channels is stereo and six is 5.1 — the number of speakers is the thing
    people know. */
const SOUND: Record<number, string> = { 1: 'mono', 2: 'stereo', 6: '5.1', 8: '7.1' };

export type Chip = {
	icon: string;
	label: string;
	to?: string;
	/** the mark the format is known by — DTS, Dolby, 4K — drawn instead of its
	 *  name where there is one for it */
	flag?: string | null;
};

// The marks we hold. A format is recognised by its mark before it is read as a
// word, and every one of these is a single white shape with alpha — the same
// language every other mark on this surface is drawn in.
const AUDIO_MARKS = new Set([
	'aac', 'ac3', 'ape', 'atmos', 'dts', 'dts_x', 'dtshd_hra', 'dtshd_ma',
	'eac3', 'flac', 'm4a', 'mp3', 'opus', 'pcm', 'truehd', 'vorbis', 'wma'
]);

const SCREEN_MARKS: Record<string, string> = {
	'2160p': '4K', '4k': '4K', uhd: '4K',
	'1080p': '1080', '1080i': '1080',
	'720p': '720', '576p': '576', '480p': '480'
};

/** Which mark a sound track is known by. The profile is what tells DTS from
 *  DTS-HD Master Audio and TrueHD from TrueHD with Atmos — the codec alone
 *  calls all of them by the name of the core. */
function audioMark(codec: string, profile?: string | null): string | null {
	const c = codec.toLowerCase();
	const p = (profile ?? '').toLowerCase();
	const name = c.startsWith('pcm') ? 'pcm' : c === 'dca' ? 'dts' : c;
	// The profile falls back to the track's own title, which is a word like
	// "Main" or "Commentary with Mark" as often as it is a format — so only
	// the formats that can carry those extensions are read for them.
	if (p.includes('atmos') && (name === 'truehd' || name === 'eac3')) return 'atmos';
	if (name === 'dts') {
		if (/dts[-:]x/.test(p)) return 'dts_x';
		if (/\bma\b|master audio/.test(p)) return 'dtshd_ma';
		if (/\bhra\b|high res/.test(p)) return 'dtshd_hra';
	}
	return AUDIO_MARKS.has(name) ? name : null;
}

export function chipsOf(about: About | null, pathname: string): Chip[] {
	const f = about?.file;
	const chips: Chip[] = [];
	if (f?.resolution) {
		const mark = SCREEN_MARKS[f.resolution.toLowerCase()];
		// the mark says it; saying "1080p" beside a mark that reads 1080p is the
		// same thing twice
		chips.push({
			icon: 'screen',
			label: mark ? '' : f.resolution,
			flag: mark ? `/flags/screen/${mark}.png` : null
		});
	}
	if (f?.video_codec) chips.push({ icon: 'film', label: f.video_codec.toUpperCase() });
	for (const a of f?.audio ?? []) {
		const channels = a.channels ? (SOUND[a.channels] ?? `${a.channels}ch`) : '';
		const mark = audioMark(a.codec, a.profile);
		chips.push({
			icon: 'sound',
			// with a mark for the format, what is left to say is whose voice it
			// is and how many speakers it wants
			label: [(a.lang || '—').toUpperCase(), mark ? '' : a.codec.toUpperCase(), channels]
				.filter(Boolean)
				.join(' '),
			flag: mark ? `/flags/audio/${mark}.png` : null
		});
	}
	for (const lang of f?.subtitles ?? []) chips.push({ icon: 'text', label: lang.toUpperCase() });
	if (f?.size) chips.push({ icon: 'disk', label: formatBytes(f.size) });
	if (f?.container) chips.push({ icon: 'box', label: f.container.toUpperCase() });
	// three companies is who made it; the fourth is a co-production credit, and
	// this is a screen and not a title card
	for (const studio of (about?.studios ?? []).slice(0, 3)) {
		chips.push({
			icon: 'studio',
			label: studio.name,
			to: studio.id ? `${sectionOf(pathname)}?company=${studio.id}` : undefined
		});
	}
	return chips;
}
