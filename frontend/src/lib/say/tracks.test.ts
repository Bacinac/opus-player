import { describe, expect, test } from 'vitest';
import { languageOf, offeredSubtitles, soundName, subtitleName } from './tracks';
import type { PlanSubtitle } from '$lib/keep/types';

describe('soundName', () => {
	test('says the language, the channels through the formatter, and the codec', () => {
		expect(soundName({ lang: 'en', channels: 6, codec: 'eac3' })).toBe('EN · 6 kan. · eac3');
	});

	test('leaves out what is not known', () => {
		expect(soundName({ lang: '', channels: null, codec: 'aac' })).toBe('aac');
	});
});

describe('languageOf', () => {
	test('reads the language out of a macrolanguage code', () => {
		expect(languageOf('hbs-hrv')).toBe('hrv');
	});

	test('keeps a plain code', () => {
		expect(languageOf('en')).toBe('en');
	});

	test('gives nothing for what is not a language', () => {
		expect(languageOf('und-subtitles')).toBe('');
		expect(languageOf('')).toBe('');
	});
});

describe('subtitleName', () => {
	test('names a track by its language and label', () => {
		expect(subtitleName({ lang: 'hr', label: 'SDH', number: 1 })).toBe('HR · SDH');
	});

	test('a track with neither is named by its place, never as off', () => {
		expect(subtitleName({ lang: '', label: '', number: 3 })).toBe('Titl 3');
	});

	test('says forced', () => {
		expect(subtitleName({ lang: 'en', forced: true, number: 1 })).toBe('EN · prisilni');
	});
});

describe('offeredSubtitles', () => {
	const sub = (id: number, lang: string, forced = false): PlanSubtitle =>
		({ id, lang, codec: 'srt', title: '', external: false, forced }) as PlanSubtitle;

	test('the house languages first, then the rest by name, plain before forced', () => {
		const order = offeredSubtitles([sub(1, 'de'), sub(2, 'en', true), sub(3, 'en'), sub(4, 'hr'), sub(5, 'cs')]);
		expect(order.map((s) => s.id)).toEqual([4, 3, 2, 5, 1]);
	});
});
