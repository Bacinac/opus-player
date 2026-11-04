import { expect, test } from 'vitest';
import { narrower, Stalls } from './reach.js';

test('two waits inside two minutes ask for a narrower stream, one does not', () => {
	const stalls = new Stalls();
	expect(stalls.note(0)).toBe(false);
	expect(stalls.note(150_000)).toBe(false);
	expect(stalls.note(200_000)).toBe(true);
	expect(stalls.note(210_000)).toBe(false);
});

test('a narrower stream is half the last one, or what the box saw arrive when that is less', () => {
	expect(narrower(27_600)).toBe(13_800);
	expect(narrower(27_600, 3_400)).toBe(3_400);
	expect(narrower(2_450, 9_000)).toBe(1_225);
});
