import { describe, expect, test } from 'vitest';
import { art, ground } from './art';

describe('art', () => {
	test('a picture from elsewhere is fetched sized through the player', () => {
		expect(art('https://image.tmdb.org/t/p/w342/a (1).jpg', 320)).toBe(
			'/api/art?w=320&u=https%3A%2F%2Fimage.tmdb.org%2Ft%2Fp%2Fw342%2Fa%20(1).jpg'
		);
	});

	test('what the player serves itself is left alone', () => {
		expect(art('/api/photos/abc/tile', 320)).toBe('/api/photos/abc/tile');
	});

	test('no picture is no address', () => {
		expect(art(null, 320)).toBe('');
		expect(art(undefined, 320)).toBe('');
	});
});

describe('ground', () => {
	test('the wide picture first, the poster otherwise, nothing behind a station', () => {
		expect(ground({ backdrop: '/b.jpg', image: '/p.jpg' })).toBe('/b.jpg');
		expect(ground({ backdrop: null, image: 'https://x/p.jpg' })).toBe('/api/art?w=320&u=https%3A%2F%2Fx%2Fp.jpg');
		expect(ground({ kind: 'station', image: '/logo.png' })).toBeNull();
		expect(ground(null)).toBeNull();
	});
});
