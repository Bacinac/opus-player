import { describe, expect, test } from 'vitest';
import { askedOf, episodeName, haveOf, namesOf, seasonLine, seasonName, seasonViews } from './says';
import type { EpisodeEntry, SeriesTree } from '$lib/keep/types';

const episode = (id: number, playable: boolean): EpisodeEntry =>
	({ kind: 'episode', id, number: id, title: '', state: playable ? 'complete' : 'wanted', playable, resolution: null, air_date: null }) as EpisodeEntry;

describe('seasons', () => {
	const tree = {
		seasons: [
			{ number: 1, followed: true, episodes: [episode(1, true), episode(2, false), episode(3, true)] },
			{ number: 2, followed: false, episodes: [episode(4, false)] }
		]
	} as SeriesTree;

	test('a season counts what is here out of what there is', () => {
		const [first] = seasonViews(tree);
		expect([first.number, first.have, first.total]).toEqual([1, 2, 3]);
	});

	test('a season says what was watched and how much there is', () => {
		expect(seasonLine(seasonViews(tree)[0])).toBe('0 pogledano · 3 ukupno');
	});

	test('a season nobody follows says only that', () => {
		expect(seasonLine(seasonViews(tree)[1])).toBe('Ignorirano');
	});

	test('no tree is no seasons', () => {
		expect(seasonViews(null)).toEqual([]);
	});

	test('a season and a count read through the formatter', () => {
		expect(seasonName(2)).toBe('Sezona 2');
		expect(haveOf(1200, 3400)).toBe('1.200/3.400');
	});

	test('an episode without a title is named by its code', () => {
		expect(episodeName(3, episode(7, true))).toBe('S03E07');
	});
});

describe('namesOf', () => {
	test('one, two and three names', () => {
		expect(namesOf([])).toBe('');
		expect(namesOf(['Filip'])).toBe('Filip');
		expect(namesOf(['Filip', 'Kata'])).toBe('Filip i Kata');
		expect(namesOf(['Filip', 'Kata', 'Jana'])).toBe('Filip, Kata i Jana');
	});

	test('the rest counted rather than recited', () => {
		expect(namesOf(['Filip', 'Kata', 'Jana', 'Eva', 'Petra'])).toBe('Filip, Kata, Jana i još 2');
	});
});

describe('askedOf', () => {
	test('each kind of question has its own words', () => {
		const said = new Set((['who', 'where', 'when'] as const).map(askedOf));
		expect(said.size).toBe(3);
	});
});
