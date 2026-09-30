// The remote's transport keys, wherever the box is not holding them itself.
//
// A film, and a record played by the box's own engine, are answered by that
// engine's media session: the system hands it the key and the page hears about
// it as an order (`window.opusTvKey` → `cast.obey`). A record playing anywhere
// ELSE has no session at all — the DAC is a player in another room and the box
// is idle — so the key arrives here as an ordinary press, and without this
// stop would stop a film and do nothing to a record.
//
// Only what the box is NOT playing is answered here: a key its session has
// already acted on would be acted on twice, and while stopping twice is still
// stopped, pausing twice is a key that does nothing at all.

import { artist, record } from '$lib/ask/puton';
import { cast } from '$lib/keep/cast.svelte';
import { queue } from '$lib/keep/queue.svelte';
import { onBox } from '$lib/tv/bridge';

const ORDERS: Record<string, string> = {
	MediaPlayPause: 'play_pause',
	MediaPlay: 'play',
	MediaPause: 'pause',
	MediaStop: 'stop',
	MediaTrackNext: 'next',
	MediaTrackPrevious: 'previous',
	MediaFastForward: 'forward',
	MediaRewind: 'back'
};

function boxIsPlaying(): boolean {
	const said = onBox((box) => box.state());
	if (!said) return false;
	try {
		return Boolean((JSON.parse(said) as { playing?: boolean }).playing);
	} catch {
		return false;
	}
}

/** Nothing is on anywhere: the play key puts on what the remote is standing on,
 *  without opening it. Anywhere else the key is left alone. */
function putOn(): boolean {
	const perch = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-perch]');
	const [kind, id] = (perch?.dataset.perch ?? '').split(':');
	if (kind === 'release') void record(Number(id));
	else if (kind === 'artist') void artist(Number(id));
	else return false;
	return true;
}

export function playKey(event: KeyboardEvent) {
	const order = ORDERS[event.key];
	if (!order) return;
	if (boxIsPlaying()) return;
	if (!queue.current) {
		if ((order === 'play_pause' || order === 'play') && putOn()) event.preventDefault();
		return;
	}
	cast.obey(order);
	event.preventDefault();
}
