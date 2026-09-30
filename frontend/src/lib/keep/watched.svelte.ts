// What this profile has already seen.
//
// Kept by the player and nobody else: the library knows what exists, not who
// watched it, and two people in the same house are not in the same place in the
// same series. Asked for a whole list at once, because a season is twenty-two
// questions with one answer.

import { json, request } from '$lib/kit';

class WatchedState {
	private seen = $state(new Map<string, Set<number>>());
	private partly = $state(new Map<string, Map<number, number>>());

	has(kind: string, id: number): boolean {
		return this.seen.get(kind)?.has(id) ?? false;
	}

	/** How far into it this profile got and stopped, 0 to 1; 0 once it is seen. */
	part(kind: string, id: number): number {
		return this.partly.get(kind)?.get(id) ?? 0;
	}

	/** How many of these have been seen — a season's own count, said once. */
	count(kind: string, ids: number[]): number {
		const set = this.seen.get(kind);
		return set ? ids.filter((id) => set.has(id)).length : 0;
	}

	/** The answer is about the ids asked and nothing else: a film asked about
	 *  on its own says nothing about the series whose ticks are already here. */
	async ask(kind: string, ids: number[]) {
		if (!ids.length) return;
		const answer = await request<{ watched: number[]; partly: Record<string, number> }>(
			`/api/progress/watched/${kind}?ids=${ids.join(',')}`
		);
		if (!answer) return;
		const seen = new Set(answer.watched);
		this.mark(kind, ids, (id) => seen.has(id));
		const parts = new Map(this.partly.get(kind) ?? []);
		for (const id of ids) {
			const got = answer.partly[String(id)];
			if (got) parts.set(id, got);
			else parts.delete(id);
		}
		this.partly = new Map(this.partly).set(kind, parts);
	}

	async say(kind: string, ids: number[], watched: boolean, parent?: number) {
		if (!ids.length) return;
		const answer = await request(
			`/api/progress/watched`,
			json({ kind, item_ids: ids, watched, parent_id: parent ?? null })
		);
		if (!answer) return;
		this.mark(kind, ids, () => watched);
	}

	private mark(kind: string, ids: number[], seen: (id: number) => boolean) {
		const set = new Set(this.seen.get(kind) ?? []);
		for (const id of ids) {
			if (seen(id)) set.add(id);
			else set.delete(id);
		}
		this.seen = new Map(this.seen).set(kind, set);
	}
}

export const watched = new WatchedState();
