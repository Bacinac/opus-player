import { afterEach, describe, expect, test } from 'vitest';
import { playKey } from './playkey';
import { queue, type QueueTrack } from '$lib/keep/queue.svelte';

const track = (id: number): QueueTrack => ({
	id,
	position: id,
	title: `t${id}`,
	artist: 'Haustor',
	album: 'Haustor',
	cover_url: null,
	duration_s: 200
});

const press = (key: string) => ({ key, preventDefault() {} }) as KeyboardEvent;

afterEach(() => queue.clear());

describe('the remote keys', () => {
	test('stop stops a record the box itself is not playing', () => {
		queue.play([track(1), track(2)]);
		playKey(press('MediaStop'));
		// the DAC is a player in another room: no media session holds this key,
		// so the page is the only thing that can answer it
		expect(queue.current).toBe(null);
	});

	test('pause and play are the record, not a shelf', () => {
		queue.play([track(1)]);
		playKey(press('MediaPause'));
		expect(queue.playing).toBe(false);
		playKey(press('MediaPlay'));
		expect(queue.playing).toBe(true);
	});

	test('a key nothing is playing for is left alone', () => {
		playKey(press('MediaStop'));
		expect(queue.current).toBe(null);
	});
});
