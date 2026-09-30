// What a place can actually do with sound and picture — asked of the place
// itself, and asked again every time something is played.
//
// One answer for every screen: three answers to one question is how a
// two-channel record goes to the amplifier from one screen and out of the
// television's own speakers from another, and how a 7.1 film comes out of the
// room as a pair of speakers.
//
// Nothing here is cached: the same box reports `ac3, eac3` and then
// `ac3, eac3, dts, dca, truehd` minutes apart once the amplifier is moved onto
// its input, so a table of what each box can do would be wrong half the day.

import { playOf } from '$lib/opus/photos';
import { hasEngine } from '$lib/keep/queue.svelte';
import { onBox } from '$lib/tv/bridge';

export type Ability = {
	/** what it can render — decoded here, or handed whole to an amplifier */
	codecs: string[];
	/** for sound handed over whole, the most channels of it this place will take.
	    A codec it accepts in stereo and refuses in 7.1 is the difference between
	    a film and a film with no sound at all. */
	widest: Record<string, number>;
	/** how many channels can actually leave it */
	channels: number;
	/** the panel behind it, in real pixels rather than css ones */
	width: number;
	height: number;
	/** an engine of its own rather than this page */
	engine: boolean;
};

/** what a browser opens for sound wherever it runs */
const BROWSER_CODECS = ['aac', 'mp3', 'flac', 'opus', 'vorbis'];

const MIME: Record<string, string> = {
	h264: 'video/mp4; codecs="avc1.640028"',
	hevc: 'video/mp4; codecs="hvc1.1.6.L120.90"',
	av1: 'video/mp4; codecs="av01.0.05M.08"',
	vp9: 'video/mp4; codecs="vp09.00.10.08"'
};

/** The panel's real pixels, not its css ones: a 4K laptop reports 1440 wide in
 *  css and would be sent a picture softer than its screen. */
function panel(): { width: number; height: number } {
	const ratio = window.devicePixelRatio || 1;
	return {
		// the SCREEN, not the window: a picture re-encoded for the window would
		// have to be re-encoded again the moment the window changed size, and
		// going full screen is exactly when that happens
		width: Math.min(Math.round(window.screen.width * ratio), 3840),
		height: Math.min(Math.round(window.screen.height * ratio), 2160)
	};
}

/** This place, right now. */
export function here(): Ability {
	if (hasEngine()) {
		const said = onBox(
			(box) =>
				JSON.parse(box.probe()) as {
					w?: number;
					h?: number;
					audio?: string[];
					channels?: number;
					widest?: Record<string, number>;
				}
		);
		// an engine that will not say what it is gets the least we can assume
		if (!said) return { codecs: [], widest: {}, channels: 2, width: 1920, height: 1080, engine: true };
		return {
			codecs: (said.audio ?? []).map((c) => c.toLowerCase()),
			widest: said.widest ?? {},
			channels: said.channels ?? 2,
			width: said.w ?? 3840,
			height: said.h ?? 2160,
			engine: true
		};
	}
	const seen = panel();
	return {
		codecs: BROWSER_CODECS,
		widest: {},
		// a browser hands the machine two channels whatever the file holds
		channels: 2,
		...seen,
		engine: false
	};
}

/** Whether this place can be handed this sound track as it is.
 *
 *  Both halves matter. The engine was asked whether it takes the codec, said
 *  yes, and then refused the track because the question it actually asks
 *  carries the channel count too — a 7.1 track where 5.1 was the answer. The
 *  film played for two hours in silence with a perfect picture. */
export function hears(place: Ability, codec: string, channels: number): boolean {
	const name = (codec ?? '').toLowerCase();
	if (!place.codecs.includes(name)) return false;
	const most = place.widest[name];
	return most === undefined || !channels || channels <= most;
}

/** Whether this place decodes a picture well enough to be worth handing it one.
 *
 *  An engine opens the containers this library is actually in and decodes them
 *  on hardware built for it; the question is a browser's. A capability query
 *  that never answers must not be able to stop a film from starting, so no
 *  answer is read as "not efficiently". */
export async function decodes(
	place: Ability,
	codec: string,
	width: number,
	height: number
): Promise<boolean> {
	if (place.engine) return true;
	return browserDecodes(codec, width, height);
}

async function browserDecodes(codec: string, width: number, height: number): Promise<boolean> {
	const type = MIME[(codec ?? '').toLowerCase()];
	if (!type || !navigator.mediaCapabilities) return false;
	try {
		const asked = navigator.mediaCapabilities.decodingInfo({
			type: 'file',
			video: { contentType: type, width, height, bitrate: 8_000_000, framerate: 24 }
		});
		const info = await Promise.race([
			asked,
			new Promise<null>((done) => setTimeout(() => done(null), 1500))
		]);
		return Boolean(info && info.supported && info.smooth && info.powerEfficient);
	} catch {
		return false;
	}
}

const RECORDED = ['hevc', 'vp9', 'av1'];
let recorded: string[] = [];
let recording: Promise<void> | null = null;

/** Which pictures a household recording may come in, asked of the page and not
 *  of the place: the television app plays these in its page, not in its engine.
 *  Asked once, when photographs are first shown — a browser's decoders do not
 *  change under it the way a box's sound outputs do. */
export function askRecordings(): void {
	recording ??= (async () => {
		const found: string[] = [];
		for (const codec of RECORDED) if (await browserDecodes(codec, 1920, 1080)) found.push(codec);
		recorded = found;
	})();
}

/** Where a household recording plays from on this page. Until the page has
 *  answered, only h264 is claimed and the server rebuilds the rest. */
export function recordingOf(id: string): string {
	return recorded.length ? `${playOf(id)}?decodes=${recorded.join(',')}` : playOf(id);
}

/** The same sentence for the server, wherever it is asked from: what this place
 *  can be handed, how big its screen is, and which sound track it wants. The
 *  server decides the form — untouched, repackaged or re-encoded — from this
 *  and nothing else. */
export function asked(place: Ability, opts: {
	canDecode?: boolean;
	audio?: number;
	native?: boolean;
	rebuildAudio?: boolean;
} = {}): string {
	const parts = [
		`can_decode=${opts.canDecode ? 1 : 0}`,
		`max_height=${place.height}`,
		`max_width=${place.width}`,
		`audio=${opts.audio ?? 0}`,
		`native=${opts.native ? 1 : 0}`,
		`rebuild_audio=${opts.rebuildAudio ? 1 : 0}`,
		`channels=${place.channels}`,
		`accepts=${encodeURIComponent(place.codecs.join(','))}`
	];
	return parts.join('&');
}
