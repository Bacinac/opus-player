import { describe, expect, test } from 'vitest';
import { count, fact } from './count';

describe('count', () => {
	test('three Croatian forms', () => {
		expect(count(1, 'releases').text).toBe('1 izdanje');
		expect(count(3, 'releases').text).toBe('3 izdanja');
		expect(count(1200, 'releases').text).toBe('1.200 izdanja');
	});

	test('painted as its kind', () => {
		expect(count(2, 'movies')).toMatchObject({ kind: 'film', icon: 'film' });
		expect(count(2, 'places')).toMatchObject({ tone: 'fact', icon: 'pin' });
	});

	test('a fact keeps what it is given', () => {
		expect(fact('1979 – 1990', 'years')).toEqual({ text: '1979 – 1990', icon: 'years', tone: 'fact' });
	});
});
