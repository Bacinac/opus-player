import { describe, expect, test } from 'vitest';
import { winners } from './awards';
import type { Card } from './types';

const card = (id: number, won: Record<string, number[]>): Card =>
	({ kind: 'movie', id, title: `t${id}`, image: null, backdrop: null, state: null, overview: '', won }) as Card;

const WALL = [
	card(1, { oscar: [2020] }),
	card(2, { palme_dor: [2019], oscar: [2020] }),
	card(3, { bafta: [2024] }),
	card(4, { golden_lion: [2022], bafta: [2023] })
];
const shown = (only: string[], without: string[]) =>
	winners(WALL, { only, without }).map((c) => [c.id, c.subtitle]);

describe('winners', () => {
	test('at rest every winner stands, the most recent win first', () => {
		expect(shown([], [])).toEqual([[3, '2024'], [4, '2022, 2023'], [1, '2020'], [2, '2019, 2020']]);
	});

	test('an award asked for alone keeps its winners and their years for it', () => {
		expect(shown(['oscar'], [])).toEqual([[1, '2020'], [2, '2020']]);
		expect(shown(['oscar', 'bafta'], [])).toEqual([[3, '2024'], [4, '2023'], [1, '2020'], [2, '2020']]);
	});

	test('an award left out takes every title that won it off the wall', () => {
		expect(shown([], ['oscar'])).toEqual([[3, '2024'], [4, '2022, 2023']]);
		expect(shown(['bafta'], ['golden_lion'])).toEqual([[3, '2024']]);
	});
});
