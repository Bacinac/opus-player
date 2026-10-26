import { describe, expect, it } from 'vitest';

import { compareHr, initialOf, lettersOf } from '#lib/kit/index.js';

describe('a band files under its name, not its article', () => {
	it('The Doors stand under D and sort between Dalibor and Dubioza', () => {
		expect(initialOf('The Doors')).toBe('D');
		expect(initialOf('the the')).toBe('T');
		const shelf = ['Dubioza Kolektiv', 'The Doors', 'Dalibor Brun', 'Theodora', 'Ljubav'];
		expect(shelf.toSorted(compareHr)).toEqual([
			'Dalibor Brun', 'The Doors', 'Dubioza Kolektiv', 'Ljubav', 'Theodora'
		]);
		expect(lettersOf(shelf.toSorted(compareHr))).toEqual(['D', 'Lj', 'T']);
	});
});
