// @vitest-environment happy-dom
import { afterEach, expect, test, vi } from 'vitest';
import { flushSync, mount, unmount } from 'svelte';
import FilmRequest from './FilmRequest.test.svelte';
import { film } from '#lib/keep/film.svelte.js';
import { surface } from '#lib/keep/surface.svelte.js';
import { FilmEngine } from '#lib/tv/filmEngine.svelte.js';
import type { Card, Plan } from '#lib/keep/types.js';

let host: ReturnType<typeof mount> | null = null;
const reports: { kind: string; item_id: number; position_s: number }[] = [];
let stalls = 0;
const slower: (number | undefined)[] = [];
const card = (kind: Card['kind'], id: number): Card => ({
	kind, id, title: String(id), image: null, backdrop: null, state: 'complete', overview: ''
});

afterEach(async () => {
	if (host) await unmount(host);
	host = null;
	film.close();
	film.current = null;
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	delete window.opusTv;
	reports.length = 0;
	stalls = 0;
	slower.length = 0;
	document.body.innerHTML = '';
});

async function open(initial: Card, rebuilt = false) {
	surface.current = 'tv';
	window.opusTv = {
		saveFile: vi.fn(() => ''), fileState: vi.fn(() => '{"state":"cancelled"}'),
		writeFile: vi.fn(() => -1), finishFile: vi.fn(() => false), cancelFile: vi.fn(),
		engine: () => 'media3', probe: () => '{}', plugged: () => '', canVideo: () => true,
		play: vi.fn(), toggle: vi.fn(), seek: vi.fn(), stop: vi.fn(), captionsUp: vi.fn(),
		chooseAudio: vi.fn(), chooseText: vi.fn(),
		state: () => JSON.stringify({ position: 120, duration: 1800, playing: true, ended: false,
			audio: [], text: [], decoder: 'test', dropped: 0, picture: '1920×1080', stalls, bandwidth: 0 })
	};
	vi.stubGlobal('fetch', async (url: RequestInfo | URL, options?: RequestInit) => {
		if (String(url) === '/api/progress' && options?.body)
			reports.push(JSON.parse(String(options.body)));
		const data = String(url).includes('/api/progress/') ? { position_s: 120 } : { boxes: [], ok: true };
		return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
	});
	vi.spyOn(FilmEngine.prototype, 'plan').mockImplementation(async function (
		this: FilmEngine, _card: Card, _audio: number, _refused: unknown, under?: number
	) {
		slower.push(under);
		this.rebuilt = rebuilt || under !== undefined;
		return { audio: 0, plan: {
			mode: under ? 'transcode' : rebuilt ? 'remux' : 'direct', kbps: under ? Math.round(under * 0.7) : 27_600,
			title: 'Test', duration_s: 1800, subtitles: [], audio: [], chapters: [],
			source: { video_codec: 'h264', width: 1920, height: 1080, frame_rate: 24 },
			next: { id: 3381, season_number: 2, number: 2, title: 'Next' }
		} as unknown as Plan };
	});
	film.ask(initial);
	flushSync(() => { host = mount(FilmRequest, { target: document.body }); });
	await vi.waitFor(() => expect(window.opusTv?.play).toHaveBeenCalledOnce());
	await new Promise((resolve) => setTimeout(resolve, 550));
	flushSync();
}

test('closing a requested film keeps its card for the final progress report', async () => {
	await open(card('movie', 105));
	expect(() => flushSync(() => film.close())).not.toThrow();
	expect(reports).toContainEqual(expect.objectContaining({ kind: 'movie', item_id: 105, position_s: 120 }));
});

test('replacing a requested film reports the outgoing item before the successor starts', async () => {
	await open(card('movie', 105));
	expect(() => flushSync(() => film.ask(card('episode', 3380)))).not.toThrow();
	await vi.waitFor(() => expect(window.opusTv?.play).toHaveBeenCalledTimes(2));
	expect(reports).toContainEqual(expect.objectContaining({ kind: 'movie', item_id: 105, position_s: 120 }));
	expect(reports.some((report) => report.kind === 'episode')).toBe(false);
});

test('the next episode retains the previous episode through close and replacement', async () => {
	await open(card('episode', 3380));
	expect(() => flushSync(() => film.current?.episode())).not.toThrow();
	await vi.waitFor(() => expect(window.opusTv?.play).toHaveBeenCalledTimes(2));
	expect(film.asked?.id).toBe(3381);
	expect(reports).toContainEqual(expect.objectContaining({ kind: 'episode', item_id: 3380, position_s: 120 }));
});

test('a held arrow on a rebuilt stream starts it once, where the keys stop', async () => {
	await open(card('movie', 105), true);
	const play = window.opusTv?.play as ReturnType<typeof vi.fn>;
	const from = film.current!.position();
	for (let step = 1; step <= 5; step++) {
		film.current!.seek(film.current!.position() + 10);
		await new Promise((resolve) => setTimeout(resolve, 50));
	}
	flushSync();
	expect(film.current!.position()).toBe(from + 50);
	expect(play).toHaveBeenCalledOnce();
	await vi.waitFor(() => expect(play).toHaveBeenCalledTimes(2));
	expect(String(play.mock.calls[1][0])).toContain(`&t=${Math.floor(from + 50)}`);
	await new Promise((resolve) => setTimeout(resolve, 500));
	expect(play).toHaveBeenCalledTimes(2);
});

test('a film that keeps stopping for data is asked for again narrower, from where it is', async () => {
	await open(card('movie', 105));
	const play = window.opusTv?.play as ReturnType<typeof vi.fn>;
	stalls = 1;
	await new Promise((resolve) => setTimeout(resolve, 550));
	flushSync();
	expect(slower).toEqual([undefined]);
	stalls = 2;
	await vi.waitFor(() => expect(play).toHaveBeenCalledTimes(2));
	expect(slower).toEqual([undefined, 13_800]);
	expect(String(play.mock.calls[1][0])).toContain('&t=120');
});
