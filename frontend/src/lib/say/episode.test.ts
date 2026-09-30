import { afterEach, describe, expect, test, vi } from 'vitest';
import { aired, episodeLabel, episodeState, spoken, stateOf } from './episode';
import type { Card, EpisodeEntry } from '$lib/keep/types';

const episode = (over: Partial<EpisodeEntry>): EpisodeEntry =>
	({ id: 1, number: 2, title: 'Pilot', state: 'complete', playable: true, air_date: '2011-04-17', ...over }) as EpisodeEntry;

afterEach(() => {
	vi.useRealTimers();
});

describe('episodeLabel', () => {
	test('the code and the title', () => {
		expect(episodeLabel(1, { number: 2, title: 'Pilot' })).toBe('S01E02 · Pilot');
	});

	test('the code alone without a title', () => {
		expect(episodeLabel(10, { number: 12, title: '' })).toBe('S10E12');
	});
});

describe('state', () => {
	test('an unknown state reads as wanted', () => {
		expect(stateOf(episode({ state: 'something' }))).toBe('state.wanted');
	});

	test('an episode not yet broadcast is upcoming, not wanted', () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2026-09-17T12:00:00Z'));
		const later = episode({ state: 'wanted', air_date: '2026-10-01' });
		expect(aired(later)).toBe(false);
		expect(episodeState(later)).toBe('Još nije emitirana');
		expect(aired(episode({ air_date: null }))).toBe(true);
	});
});

describe('spoken', () => {
	test('an episode card says its code and title under the series', () => {
		const card = { kind: 'episode', id: 5, title: 'Ergo', season_number: 2, number: 3, episode_title: 'Three' } as Card;
		expect(spoken(card).subtitle).toBe('S02E03 · Three');
	});

	test('anything else is left as it came', () => {
		const card = { kind: 'movie', id: 1, title: 'Alien', subtitle: 1979 } as Card;
		expect(spoken(card)).toBe(card);
	});
});
