import { beforeEach, describe, expect, test } from 'vitest';
import { queue, type QueueTrack } from './queue.svelte';

const track = (id: number, over: Partial<QueueTrack> = {}): QueueTrack => ({
	id,
	position: id,
	title: `t${id}`,
	artist: 'Haustor',
	album: 'Haustor',
	cover_url: null,
	duration_s: 200,
	...over
});

beforeEach(() => {
	queue.clear();
});

describe('queue', () => {
	test('a record plays from the song pressed, and the rest follows', () => {
		queue.play([track(1), track(2), track(3)], 1);
		expect(queue.current?.id).toBe(2);
		expect(queue.src).toBe('/api/play/track/2/stream');
		expect(queue.nextSrc).toBe('/api/play/track/3/stream');
		queue.next();
		expect(queue.current?.id).toBe(3);
		expect(queue.hasNext).toBe(false);
		queue.next();
		// played through, and let go: the bar along the bottom is what is playing,
		// so a record that has finished leaves nothing to stand there
		expect(queue.playing).toBe(false);
		expect(queue.current).toBe(null);
	});

	test('a station that stops is dropped, not finished', () => {
		queue.play([track(0, { url: 'http://radio/x', play_url: '/api/radio/stream?u=x', live: true })]);
		queue.next();
		expect(queue.playing).toBe(false);
		// still there to be started again: a stream has no end to have reached
		expect(queue.current?.url).toBe('http://radio/x');
	});

	test('where to start is held within the record', () => {
		queue.play([track(1), track(2)], 9, 30);
		expect(queue.index).toBe(1);
		expect(queue.startAt).toBe(30);
		queue.jump(0);
		expect(queue.startAt).toBe(0);
		queue.jump(5);
		expect(queue.index).toBe(0);
	});

	test('a station plays from its own address and nothing is faded into after it', () => {
		queue.play([track(1), track(0, { url: 'http://radio/x', play_url: '/api/radio/stream?u=x', live: true })]);
		expect(queue.srcAt(1)).toBe('/api/radio/stream?u=x');
		expect(queue.nextSrc).toBe('');
	});
});
