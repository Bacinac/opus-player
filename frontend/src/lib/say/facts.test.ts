import { describe, expect, test } from 'vitest';
import { aboutArtist, aboutWork, streamingOn } from './facts';
import type { About, Card } from '$lib/keep/types';

const card = (over: Partial<Card>): Card => ({ kind: 'artist', id: 1, title: 'Haustor', image: null, backdrop: null, state: null, overview: '', ...over }) as Card;

describe('aboutArtist', () => {
	test('the years, the country and the releases', () => {
		expect(aboutArtist(card({ year: 1979, end_year: 1990, country: 'HR', releases: 6 }))).toBe('1979 – 1990 · HR · 6 izdanja');
	});

	test('still going', () => {
		expect(aboutArtist(card({ year: 1979 }))).toBe('od 1979.');
	});
});

describe('streamingOn', () => {
	const netflix = { id: 8, name: 'Netflix', logo: null, ours: true };

	test('only what is out in the world and streams somewhere', () => {
		expect(streamingOn(card({ owned: false, streaming: [netflix] }))).toBe('Dostupno na: Netflix');
		expect(streamingOn(card({ streaming: [netflix] }))).toBe('');
		expect(streamingOn(card({ owned: false, streaming: null }))).toBe('');
		expect(streamingOn(null)).toBe('');
	});
});

describe('aboutWork', () => {
	test('the year, the length through the formatter and the genres by name', () => {
		const about = { overview: '', year: 1979, runtime_min: 1117, genres: ['Drama', 'Something New'] } as About;
		expect(aboutWork(about)).toBe('1979 · 1.117 min · Drama · Something New');
	});

	test('nothing known is nothing said', () => {
		expect(aboutWork(null)).toBe('');
	});
});
