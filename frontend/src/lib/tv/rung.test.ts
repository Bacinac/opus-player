// @vitest-environment happy-dom
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { at, draw, focused } from '$lib/tvui/testing';

const goto = vi.hoisted(() => vi.fn());
vi.mock('$app/navigation', () => ({ goto }));

import { rung } from './rung.svelte';

const url = (path: string) => new URL(path, 'http://tv.test');

const MENU = `
	<nav class="rail">
		<a href="/movies" id="movies" data-box="40 100 120 30"></a>
		<a href="/series" id="series" class="here" data-box="40 140 120 30"></a>
	</nav>
	<main><a href="#" class="card" id="c1" data-box="200 100 100 150"></a></main>`;

beforeEach(() => {
	goto.mockClear();
	rung.leaving = false;
	draw(MENU);
});

describe('back on a television', () => {
	test('from a page is its section’s shelf', () => {
		expect(rung.climb(url('/series/12/s/2'))).toBe(true);
		expect(goto).toHaveBeenCalledWith('/series', { replaceState: true });
	});

	test('from a question is the page it was asked from, once', () => {
		const asked = url('/movies?person=31');
		rung.went(url('/movies/7'), asked);
		expect(rung.asked(asked)).toBe(true);
		rung.climb(asked);
		expect(goto).toHaveBeenCalledWith('/movies/7', { replaceState: true });
		expect(rung.asked(asked)).toBe(false);
	});

	test('does not remember going somewhere that is not a question', () => {
		rung.went(url('/movies'), url('/movies/7'));
		expect(rung.asked(url('/movies/7'))).toBe(false);
	});

	test('from a section’s shelf is the menu, on that section', () => {
		at('#c1').focus();
		expect(rung.holds(url('/series'))).toBe(true);
		rung.climb(url('/series'));
		expect(focused()?.id).toBe('series');
		expect(rung.leaving).toBe(false);
	});

	test('from the menu offers the way out, and back again takes the offer away', () => {
		at('#series').focus();
		expect(rung.holds(url('/series'))).toBe(false);
		rung.climb(url('/series'));
		expect(rung.leaving).toBe(true);
		expect(rung.holds(url('/series'))).toBe(true);
		rung.climb(url('/series'));
		expect(rung.leaving).toBe(false);
		expect(goto).not.toHaveBeenCalled();
	});
});
