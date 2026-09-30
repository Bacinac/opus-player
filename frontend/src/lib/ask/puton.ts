// Putting something on without opening it first: a record, a whole artist, or
// the place in a record somebody left. The same three sentences from a row, a
// sleeve and the play key on the remote.

import { request } from '$lib/kit';
import { hasEngine, queue, type QueueTrack } from '$lib/keep/queue.svelte';
import type { Card, ReleaseQueue } from '$lib/keep/types';

// the edition this screen can actually play: only the box's own player hears
// more than two channels
const prefer = () => (hasEngine() ? 'surround' : 'stereo');

export async function record(releaseId: number, from = 0, at = 0) {
	const album = await request<ReleaseQueue>(`/api/library/release/${releaseId}?prefer=${prefer()}`);
	if (album?.tracks.length) queue.play(album.tracks, from, at);
}

export async function artist(artistId: number, shuffle = false) {
	const found = await request<{ tracks: QueueTrack[] }>(
		`/api/library/artist/${artistId}/queue?prefer=${prefer()}${shuffle ? '&shuffle=true' : ''}`
	);
	if (found?.tracks.length) queue.play(found.tracks);
}

/** A song out of the row of what was left in the middle. One song is a place
 *  in a record, so the record goes back on — at that song, at that second. */
export async function carryOn(c: Card) {
	if (!c.release_id) return;
	const album = await request<ReleaseQueue>(`/api/library/release/${c.release_id}?prefer=${prefer()}`);
	if (!album) return;
	const at = album.tracks.findIndex((track) => track.id === c.id);
	queue.play(album.tracks, Math.max(0, at), at < 0 ? 0 : (c.position_s ?? 0));
}
