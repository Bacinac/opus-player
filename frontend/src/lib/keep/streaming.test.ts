import { describe, expect, test } from 'vitest';
import { readStances, servicesOf, sift, writtenStances } from './streaming';
import type { Card, Service } from './types';

const NETFLIX: Service = { id: 8, name: 'Netflix', logo: '/netflix.png', ours: false };
const HBO: Service = { id: 384, name: 'HBO Max', logo: null, ours: true };
const DISNEY: Service = { id: 337, name: 'Disney+', logo: null, ours: false };

const card = (id: number, streaming?: Service[] | null): Card =>
	({ kind: 'movie', id, title: `t${id}`, image: null, backdrop: null, state: null, overview: '', ...(streaming === undefined ? {} : { streaming }) }) as Card;

const WALL = [
	card(1, [NETFLIX]),
	card(2, [HBO]),
	card(3, [NETFLIX, HBO]),
	card(4, [DISNEY]),
	card(5, []),
	card(6, null),
	card(7)
];
const OFFERED = servicesOf(WALL);
const ids = (cards: Card[]) => cards.map((c) => c.id);

describe('servicesOf', () => {
	test('the house first, then by how many titles', () => {
		expect(OFFERED.map((o) => o.key)).toEqual(['384', '8', '337']);
		expect(OFFERED[0]).toMatchObject({ label: 'HBO Max', image: undefined });
		expect(OFFERED[1].image).toBe('/netflix.png');
	});
});

describe('sift', () => {
	test('nothing chosen keeps the wall', () => {
		expect(ids(sift(WALL, { only: [], without: [] }, OFFERED))).toEqual([1, 2, 3, 4, 5, 6, 7]);
	});

	test('only: titles on any service asked for, and never one whose services are unknown', () => {
		expect(ids(sift(WALL, { only: ['8'], without: [] }, OFFERED))).toEqual([1, 3]);
		expect(ids(sift(WALL, { only: ['8', '337'], without: [] }, OFFERED))).toEqual([1, 3, 4]);
	});

	test('without: titles on any service left out go, the unknown and the held stay', () => {
		expect(ids(sift(WALL, { only: [], without: ['8'] }, OFFERED))).toEqual([2, 4, 5, 6, 7]);
		expect(ids(sift(WALL, { only: [], without: ['8', '384'] }, OFFERED))).toEqual([4, 5, 6, 7]);
	});

	test('mixed: only these, less those', () => {
		expect(ids(sift(WALL, { only: ['384'], without: ['8'] }, OFFERED))).toEqual([2]);
	});

	test('a stance on a service this wall does not offer says nothing', () => {
		const elsewhere = servicesOf([card(1, [NETFLIX])]);
		expect(ids(sift(WALL, { only: ['337'], without: ['384'] }, elsewhere))).toEqual([1, 2, 3, 4, 5, 6, 7]);
	});
});

describe('stances kept', () => {
	test('round trip', () => {
		const stances = { only: ['8'], without: ['384'] };
		expect(readStances(writtenStances(stances))).toEqual(stances);
	});

	test('nothing chosen is nothing kept', () => {
		expect(writtenStances({ only: [], without: [] })).toBeNull();
	});

	test('what cannot be read is ignored', () => {
		expect(readStances('8,337')).toEqual({ only: [], without: [] });
		expect(readStances(null)).toEqual({ only: [], without: [] });
		expect(readStances('{"only":[8,"337"],"without":"x"}')).toEqual({ only: ['337'], without: [] });
	});
});
