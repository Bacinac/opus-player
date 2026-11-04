// How fast the road from the server to this screen is, measured on the road the
// film will take. A box in another house decodes the 4K file perfectly and is
// handed it three times faster than its connection carries; what it can open
// says nothing about what reaches it.

const ASKED = 32 << 20;
// Past this nothing in the library needs measuring further, and a screen at home
// should not wait on a second of downloading before every film.
const PLENTY_KBPS = 150_000;
const ENOUGH_BYTES = 4 << 20;
const LONGEST_MS = 1500;

/** kbit/s, or null when nothing came back to measure: a measurement that fails
 *  must not be able to stop a film, so the film is then planned as before. */
export async function reach(): Promise<number | null> {
	const stop = new AbortController();
	const begun = performance.now();
	const late = setTimeout(() => stop.abort(), LONGEST_MS);
	let got = 0;
	let first = 0;
	let last = 0;
	try {
		const answer = await fetch(`/api/play/reach?size=${ASKED}`, { signal: stop.signal, cache: 'no-store' });
		if (!answer.ok || !answer.body) return null;
		const reader = answer.body.getReader();
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			last = performance.now();
			// the clock starts at the first bytes: the wait before them is the
			// distance to the server, which a film pays once and not per second
			if (!first) {
				first = last;
				continue;
			}
			got += value.byteLength;
			const kbps = (got * 8) / (last - first);
			if ((got >= ENOUGH_BYTES && kbps >= PLENTY_KBPS) || last - begun >= LONGEST_MS) break;
		}
		stop.abort();
	} catch {
		// cut off by the clock: what arrived until then is the measurement
	} finally {
		clearTimeout(late);
	}
	return got > 0 && last > first ? Math.round((got * 8) / (last - first)) : null;
}

// one wait is the road catching its breath; two inside two minutes is a film
// wider than the road
const STALLS = 2;
const STALL_WINDOW_MS = 120_000;

export class Stalls {
	#at: number[] = [];

	/** True when this wait means the stream should come narrower. */
	note(now = performance.now()): boolean {
		this.#at = [...this.#at.filter((then) => now - then < STALL_WINDOW_MS), now];
		if (this.#at.length < STALLS) return false;
		this.#at = [];
		return true;
	}
}

/** The connection to plan for after a stream of `kbps` kept stopping: at most
 *  half of it, and no more than the box saw its film arrive at. */
export function narrower(kbps: number, seen = 0): number {
	return Math.round(Math.min(seen > 0 ? seen : Infinity, kbps / 2));
}
