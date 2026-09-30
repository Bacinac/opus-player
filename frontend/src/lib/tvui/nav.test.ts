// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { at, draw, focused } from './testing';

const where = vi.hoisted(() => ({ url: new URL('http://tv.test/music') }));
vi.mock('$app/state', () => ({ page: where }));

import { nav } from './nav.svelte';

const go = (path: string) => (where.url = new URL(path, 'http://tv.test'));
const settle = () => new Promise<void>((done) => queueMicrotask(done));

beforeEach(() => go('/music'));

describe('the level', () => {
	test('is read off the path: a section is the menu screen, anything deeper a page', () => {
		expect(nav.level).toBe(1);
		go('/series/12/s/2');
		expect(nav.level).toBe(2);
	});

	test('a view that takes the screen raises it once mounted, and gives it back', async () => {
		const give = nav.takes();
		expect(nav.level).toBe(1);
		await settle();
		expect(nav.level).toBe(2);
		give();
		await settle();
		expect(nav.level).toBe(1);
	});

	test('a view gone before its count arrived takes nothing from another', async () => {
		const staying = nav.takes();
		await settle();
		const gone = nav.takes();
		gone();
		await settle();
		expect(nav.level).toBe(2);
		staying();
		await settle();
		expect(nav.level).toBe(1);
	});

	test('giving back twice gives back once', async () => {
		const staying = nav.takes();
		const twice = nav.takes();
		await settle();
		twice();
		twice();
		await settle();
		expect(nav.level).toBe(2);
		staying();
		await settle();
		expect(nav.level).toBe(1);
	});
});

describe('the section', () => {
	test('is the first part of the path at either level', () => {
		go('/series/12/s/2');
		expect(nav.section).toBe('/series');
		go('/');
		expect(nav.section).toBe('/');
	});
});

describe('the perch', () => {
	test('is remembered per path, from whatever took the ring', () => {
		go('/movies');
		draw(`<main><a href="#" id="r" data-perch="release:3" data-box="0 0 10 10"></a></main>`);
		nav.remember(at('#r'));
		nav.remember(document.body);
		expect(nav.perch()).toBe('release:3');
		expect(nav.perch('/radio')).toBeUndefined();
	});
});

describe('landing', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	test('goes back to the perch rather than to the first thing that will do', () => {
		go('/land-perch');
		draw(`<main>
			<button id="head" data-box="0 0 50 20"></button>
			<a href="#" class="card" id="c1" data-perch="film:1" data-box="0 100 50 80"></a>
			<a href="#" class="card" id="c2" data-perch="film:2" data-box="60 100 50 80"></a>
		</main>`);
		nav.remember(at('#c2'));
		nav.land('.card');
		vi.advanceTimersByTime(50);
		expect(focused()?.id).toBe('c2');
	});

	test('tries its fallbacks in the order given, not in document order', () => {
		go('/land-order');
		draw(`<main>
			<button id="director" data-box="0 0 50 20"></button>
			<button class="season" id="s1" data-box="0 100 50 20"></button>
		</main>`);
		nav.land(['.season', 'button']);
		vi.advanceTimersByTime(50);
		expect(focused()?.id).toBe('s1');
	});

	test('waits for the page to draw what it lands on', () => {
		go('/land-late');
		draw(`<main></main>`);
		nav.land('.card');
		vi.advanceTimersByTime(200);
		at('main').innerHTML = `<a href="#" class="card" id="late" data-box="0 0 50 80"></a>`;
		vi.advanceTimersByTime(50);
		expect(focused()?.id).toBe('late');
	});

	test('yields to the menu or to anything holding the remote', () => {
		go('/land-yield');
		draw(`
			<nav class="rail"><a href="/music" id="music" data-box="0 0 50 20"></a></nav>
			<main><a href="#" class="card" id="c1" data-box="60 0 50 80"></a></main>`);
		at('#music').focus();
		nav.land('.card');
		vi.advanceTimersByTime(500);
		expect(focused()?.id).toBe('music');
	});
});

describe('returning', () => {
	test('puts the ring on the tile it was opened from, marked as ours until it moves', async () => {
		draw(`<main>
			<a href="#" id="t1" data-perch="release:9" data-box="0 0 50 80"></a>
			<a href="#" id="t2" data-box="60 0 50 80"></a>
		</main>`);
		nav.returnTo('release:9');
		await settle();
		expect(focused()?.id).toBe('t1');
		expect(at('#t1').dataset.returned).toBe('');
		at('#t2').focus();
		expect(at('#t1').dataset.returned).toBeUndefined();
	});
});
