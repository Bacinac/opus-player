// @vitest-environment happy-dom
import { afterEach, expect, test, vi } from 'vitest';
import { flushSync, mount, unmount } from 'svelte';
import FilmRequest from './FilmRequest.test.svelte';
import { film } from '$lib/keep/film.svelte';
import { surface } from '$lib/keep/surface.svelte';
import { FilmEngine } from '$lib/tv/filmEngine.svelte';
import type { Card, Plan } from '$lib/keep/types';

let host: ReturnType<typeof mount> | null = null;
const reports: { kind: string; item_id: number; position_s: number }[] = [];
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
	document.body.innerHTML = '';
});

async function open(initial: Card) {
	surface.current = 'tv';
	window.opusTv = {
		engine: () => 'media3', probe: () => '{}', plugged: () => '', canVideo: () => true,
		play: vi.fn(), toggle: vi.fn(), seek: vi.fn(), stop: vi.fn(), captionsUp: vi.fn(),
		chooseAudio: vi.fn(), chooseText: vi.fn(),
		state: () => JSON.stringify({ position: 120, duration: 1800, playing: true, ended: false,
			audio: [], text: [], decoder: 'test', dropped: 0, picture: '1920×1080' })
	};
	vi.stubGlobal('fetch', async (url: RequestInfo | URL, options?: RequestInit) => {
		if (String(url) === '/api/progress' && options?.body)
			reports.push(JSON.parse(String(options.body)));
		const data = String(url).includes('/api/progress/') ? { position_s: 120 } : { boxes: [], ok: true };
		return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
	});
	vi.spyOn(FilmEngine.prototype, 'plan').mockResolvedValue({ audio: 0, plan: {
		mode: 'direct', title: 'Test', duration_s: 1800, subtitles: [], audio: [], chapters: [],
		source: { video_codec: 'h264', width: 1920, height: 1080, frame_rate: 24 },
		next: { id: 3381, season_number: 2, number: 2, title: 'Next' }
	} as unknown as Plan });
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
