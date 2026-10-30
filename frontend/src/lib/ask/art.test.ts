// @vitest-environment happy-dom
import { describe, expect, test } from 'vitest';
import { art, artAbroad, ground } from './art';

describe('art', () => {
	test("a library picture is asked for at the size it is drawn", () => {
		expect(art('/api/pictures/42', 320)).toBe('/api/pictures/42?w=320');
	});

	test('what the player serves itself is left alone', () => {
		expect(art('/api/photos/abc/tile', 320)).toBe('/api/photos/abc/tile');
	});

	test('somebody else\'s server is not asked', () => {
		expect(art('https://image.tmdb.org/t/p/w342/a.jpg', 320)).toBe('');
	});

	test('no picture is no address', () => {
		expect(art(null, 320)).toBe('');
		expect(art(undefined, 320)).toBe('');
	});
});

describe('artAbroad', () => {
	test('the whole address, for an engine with no page around it', () => {
		expect(artAbroad('/api/pictures/42', 640)).toBe(`${location.origin}/api/pictures/42?w=640`);
		expect(artAbroad(null, 640)).toBe('');
	});
});

describe('ground', () => {
	test('the wide picture first, the poster otherwise, nothing behind a station', () => {
		expect(ground({ backdrop: '/api/pictures/2', image: '/api/pictures/1' })).toBe('/api/pictures/2?w=780');
		expect(ground({ backdrop: null, image: '/api/pictures/1' })).toBe('/api/pictures/1?w=320');
		expect(ground({ kind: 'station', image: '/api/pictures/3' })).toBeNull();
		expect(ground(null)).toBeNull();
	});
});
