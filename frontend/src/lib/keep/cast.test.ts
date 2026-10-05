import { afterEach, describe, expect, test, vi } from 'vitest';
import { cast } from './cast.svelte';
import { film, type FilmOnTv } from './film.svelte';
import { queue, type QueueTrack } from './queue.svelte';
import { shown } from './tvPhoto.svelte';
import { surface } from './surface.svelte';

const track = (id: number): QueueTrack => ({
	id,
	position: id,
	title: `t${id}`,
	artist: 'Haustor',
	album: 'Haustor',
	cover_url: null,
	duration_s: 200
});

/** The box this page runs in, as the bridge looks for it: a window with an
 *  engine on it. These tests run without a DOM, which is also how the bridge
 *  sees a browser that is nobody's television. */
function box(): { stop: ReturnType<typeof vi.fn>; seek: ReturnType<typeof vi.fn> } {
	const engine = { engine: () => true, stop: vi.fn(), seek: vi.fn() };
	(globalThis as { window?: unknown }).window = { opusTv: engine };
	return engine;
}

afterEach(() => {
	queue.clear();
	film.current = null;
	shown.close();
	surface.current = 'desktop';
	cast.active = 'browser';
	queue.autocast = null;
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	delete (globalThis as { window?: unknown }).window;
});

test.each(['play', 'pause', 'play_pause'])('native %s reaches the engine and survives its next state report', (command) => {
	let playing = command === 'play' ? false : true;
	const engine = { engine: () => true, state: () => JSON.stringify({ playing }),
		toggle: vi.fn(() => { playing = !playing; }) };
	(globalThis as { window?: unknown }).window = { opusTv: engine };
	surface.current = 'tv';
	queue.play([track(1)]);
	cast.obey(command);
	expect(engine.toggle).toHaveBeenCalledOnce();
	expect(queue.playing).toBe(command === 'play');
	expect(JSON.parse(engine.state()).playing).toBe(queue.playing);
});

test.each(['play', 'pause'])('native %s is idempotent against engine state', (command) => {
	const engine = { engine: () => true, state: () => JSON.stringify({ playing: command === 'play' }), toggle: vi.fn() };
	(globalThis as { window?: unknown }).window = { opusTv: engine };
	surface.current = 'tv';
	queue.play([track(1)]);
	cast.obey(command);
	expect(engine.toggle).not.toHaveBeenCalled();
});

test.each(['output', 'queue', 'track', 'stop'])('a deferred cast poll cannot overwrite a new %s', async (change) => {
	let answer: (value: Response) => void = () => {};
	vi.stubGlobal('fetch', () => new Promise<Response>((resolve) => { answer = resolve; }));
	queue.play([track(1), track(2)]);
	cast.active = 'stereo';
	cast.position = 3;
	const polling = (cast as unknown as { poll(): Promise<void> }).poll();
	if (change === 'output') cast.active = 'browser';
	else if (change === 'queue') queue.play([track(9)]);
	else if (change === 'track') queue.jump(1);
	else queue.clear();
	answer(new Response(JSON.stringify({ transport: 'playing', title: 'stale station',
		position: 90, duration: 200, source: 'radio', index: 0 }),
		{ headers: { 'Content-Type': 'application/json' } }));
	await polling;
	expect(cast.position).toBe(3);
	expect(queue.current?.id ?? null).toBe(change === 'queue' ? 9 : change === 'track' ? 2 : change === 'stop' ? null : 1);
});

describe('stopping', () => {
	test('the box is told, not only the queue', () => {
		const engine = box();
		queue.play([track(1), track(2)]);

		void cast.silence();

		// the sound comes out of the box's own engine: emptying the queue takes
		// the bar away and leaves the record playing to the end
		expect(engine.stop).toHaveBeenCalledOnce();
		expect(queue.current).toBe(null);
	});

	test('nothing is asked of a box that is not there', () => {
		queue.play([track(1)]);
		void cast.silence();
		expect(queue.current).toBe(null);
	});
});

describe('the skip keys', () => {
	function showing(at: number): FilmOnTv & { seek: ReturnType<typeof vi.fn> } {
		const on = {
			kind: 'movie',
			id: 1,
			title: 'Tko pjeva zlo ne misli',
			subtitle: '1970',
			cover: null,
			position: () => at,
			duration: () => 5400,
			seek: vi.fn(),
			playing: () => true,
			toggle: vi.fn(),
			step: vi.fn(),
			episode: vi.fn(),
			stop: vi.fn()
		};
		film.current = on;
		return on;
	}

	test('a film moves by the same step as an arrow over it', () => {
		const on = showing(600);
		cast.obey('forward');
		expect(on.seek).toHaveBeenLastCalledWith(610);
		cast.obey('back');
		expect(on.seek).toHaveBeenLastCalledWith(590);
	});

	test('the house sends an episode on to the next one, not to its next chapter', () => {
		const on = showing(600);
		cast.obey('next_episode');
		expect(on.episode).toHaveBeenCalledOnce();
		expect(on.step).not.toHaveBeenCalled();
	});

	test('a stop puts the photographs away before the film under them', () => {
		const on = showing(600);
		shown.play({ person: 37 });
		expect(shown.slides).toBe('/show.html?person=37');
		cast.obey('stop');
		expect(shown.slides).toBe(null);
		expect(on.stop).not.toHaveBeenCalled();
		cast.obey('stop');
		expect(on.stop).toHaveBeenCalledOnce();
	});

	test('a record on the box engine is sought on, never before its start', () => {
		const engine = box();
		queue.play([track(1)]);
		queue.position = 4;
		cast.obey('back');
		expect(engine.seek).toHaveBeenLastCalledWith(0);
		cast.obey('forward');
		expect(engine.seek).toHaveBeenLastCalledWith(10);
		expect(queue.position).toBe(10);
	});

	test('a record with no engine under it is left alone', () => {
		queue.play([track(1)]);
		queue.position = 30;
		cast.obey('forward');
		expect(queue.position).toBe(30);
	});
});
