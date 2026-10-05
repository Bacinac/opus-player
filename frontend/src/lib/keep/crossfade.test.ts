import { afterEach, expect, test, vi } from 'vitest';
import { Crossfade } from './crossfade';
import { queue, type QueueTrack } from './queue.svelte';

const track = (id: number): QueueTrack => ({ id, position: id, title: String(id), artist: '',
	album: '', cover_url: null, duration_s: 100 });

afterEach(() => { queue.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

test.each(['pause', 'skip', 'replace'])('a %s cancels both decks and a stale callback cannot advance the queue', (action) => {
	let callback: FrameRequestCallback = () => {};
	let clock = 0;
	vi.spyOn(performance, 'now').mockImplementation(() => clock);
	vi.stubGlobal('requestAnimationFrame', (frame: FrameRequestCallback) => { callback = frame; return 7; });
	const cancel = vi.fn();
	vi.stubGlobal('cancelAnimationFrame', cancel);
	const deck = () => ({ src: '', volume: 1, currentTime: 0, pause: vi.fn() }) as unknown as HTMLAudioElement;
	const front = deck(), spare = deck();
	queue.play([track(1), track(2)]);
	const original = queue.current;
	const completed = vi.fn(() => queue.next());
	const fade = new Crossfade(vi.fn());
	fade.start(front, spare, queue.nextSrc, 5, vi.fn(),
		() => queue.playing && queue.current === original, completed);
	const stale = callback;
	if (action === 'pause') queue.playing = false;
	else if (action === 'skip') queue.next();
	else queue.play([track(9), track(10)]);
	fade.cancel();
	clock = 6000;
	stale(clock);
	expect(front.pause).toHaveBeenCalledOnce();
	expect(spare.pause).toHaveBeenCalledOnce();
	expect(cancel).toHaveBeenCalledWith(7);
	expect(completed).not.toHaveBeenCalled();
	expect(queue.current?.id).toBe(action === 'pause' ? 1 : action === 'skip' ? 2 : 9);
	expect(queue.playing).toBe(action !== 'pause');
});

test('a completed fade advances once and later cancellation preserves the new deck', () => {
	let callback: FrameRequestCallback = () => {};
	let clock = 0;
	vi.spyOn(performance, 'now').mockImplementation(() => clock);
	vi.stubGlobal('requestAnimationFrame', (frame: FrameRequestCallback) => { callback = frame; return 1; });
	vi.stubGlobal('cancelAnimationFrame', vi.fn());
	const front = { volume: 1, pause: vi.fn() } as unknown as HTMLAudioElement;
	const spare = { volume: 1, pause: vi.fn() } as unknown as HTMLAudioElement;
	const completed = vi.fn();
	const fade = new Crossfade(vi.fn());
	fade.start(front, spare, 'next', 5, vi.fn(), () => true, completed);
	clock = 5000;
	callback(clock);
	callback(clock);
	fade.cancel();
	expect(completed).toHaveBeenCalledOnce();
	expect(front.pause).toHaveBeenCalledOnce();
	expect(spare.pause).not.toHaveBeenCalled();
});
