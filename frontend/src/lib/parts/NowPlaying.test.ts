// @vitest-environment happy-dom
import { afterEach, expect, test, vi } from 'vitest';
import { flushSync, mount, unmount } from 'svelte';
import NowPlaying from './NowPlaying.svelte';
import { cast } from '$lib/keep/cast.svelte';
import { queue } from '$lib/keep/queue.svelte';
import { surface } from '$lib/keep/surface.svelte';

let bar: ReturnType<typeof mount> | null = null;
afterEach(async () => {
	if (bar) await unmount(bar);
	bar = null;
	queue.clear();
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	document.body.innerHTML = '';
});

test.each(['pause', 'clear_fade', 'clear_normal', 'skip'])('the mounted bar retires old decks after %s', async (action) => {
	const paused = new WeakMap<HTMLMediaElement, boolean>();
	vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(function(this: HTMLMediaElement) {
		paused.set(this, false);
		return Promise.resolve();
	});
	vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(function(this: HTMLMediaElement) { paused.set(this, true); });
	vi.spyOn(HTMLMediaElement.prototype, 'paused', 'get').mockImplementation(function(this: HTMLMediaElement) { return paused.get(this) ?? true; });
	const loads = vi.spyOn(HTMLMediaElement.prototype, 'src', 'set');
	let frame: FrameRequestCallback = () => {};
	let clock = 0;
	vi.spyOn(performance, 'now').mockImplementation(() => clock);
	vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frame = callback; return 1; });
	vi.stubGlobal('cancelAnimationFrame', vi.fn());
	vi.stubGlobal('fetch', async (url: RequestInfo | URL) => new Response(JSON.stringify(
		String(url).includes('lyrics') ? { source: 'test', lines: [], plain: '', instrumental: true } : {}
	), { headers: { 'Content-Type': 'application/json' } }));
	queue.autocast = null;
	cast.active = 'browser';
	surface.current = 'desktop';
	queue.play([1, 2].map((id) => ({ id, position: id, title: String(id), artist: '', album: '',
		cover_url: null, duration_s: 10 })));
	flushSync(() => { bar = mount(NowPlaying, { target: document.body }); });
	const [front, spare] = document.querySelectorAll('audio');
	expect(front).toBeDefined();
	Object.defineProperty(front, 'duration', { configurable: true, value: 10 });
	front.currentTime = 9;
	if (action !== 'clear_normal') front.dispatchEvent(new Event('timeupdate'));
	flushSync();
	await Promise.resolve();
	if (action !== 'clear_normal') expect(spare.paused).toBe(false);
	const before = loads.mock.calls.length;
	flushSync(() => {
		if (action === 'pause') queue.playing = false;
		else if (action === 'skip') queue.next();
		else queue.clear();
	});
	expect(front.paused).toBe(action !== 'skip');
	expect(spare.paused).toBe(true);
	if (action !== 'skip') {
		expect(front.currentTime).toBe(9);
		expect(loads.mock.calls).toHaveLength(before);
	}
	clock = 6000;
	frame(clock);
	flushSync();
	expect(queue.index).toBe(action === 'skip' ? 1 : 0);
	expect(queue.playing).toBe(action === 'skip');
});
