// A film this screen handed to a television. The television plays it through
// its own engine and tells the house what it is doing; this follows that report,
// so every page here can say what is on over there and still hold its keys.

import { t } from '$lib/i18n';
import { i18n, json, request, toasts } from '$lib/kit';
import type { Card } from '$lib/keep/types';

export type Box = { id: number; name: string; listening: boolean; house: boolean; wakes: boolean };

type TvNow = {
	box: number | null;
	listening: boolean;
	transport: 'idle' | 'playing' | 'paused';
	kind: string | null;
	item_id: number | null;
	title: string;
	artist: string;
	cover_url: string | null;
	position: number | null;
	duration: number | null;
};

type OnTv = {
	box: { id: number; name: string };
	kind: string;
	id: number;
	title: string;
	subtitle: string;
	cover: string | null;
};

/** the televisions something can be sent to: those listening, and the house's
 *  own while it sleeps, which the house wakes for it */
export async function televisions(): Promise<Box[]> {
	const got = await request<{ boxes: Box[] }>('/api/tv/boxes', {}, { failed: () => {} });
	return got?.boxes.filter((box) => box.listening || box.wakes) ?? [];
}

const FILMS = new Set(['movie', 'episode']);
const POLL_MS = 2500;
// a television may first be woken and have the player opened on it, then asks
// for the film's plan and opens its stream before it says a word about it; one
// that has said nothing by now did not take it
const TAKE_MS = 60000;
// the television reports every two seconds, so the report after a key may still
// be from before it; the key's answer stands until the next one can have seen it
const HOLD_MS = 3000;
// between two episodes the television closes one film and says nothing until
// its engine has the next; silence shorter than this is that, not the end
const QUIET_MS = 20000;

class TvFilm {
	on = $state.raw<OnTv | null>(null);
	position = $state(0);
	duration = $state(0);
	playing = $state(false);
	/** the television has said it is playing this film */
	started = $state(false);

	private sent = 0;
	private held = 0;
	private quiet = 0;
	private poller: ReturnType<typeof setInterval> | null = null;
	private clock: ReturnType<typeof setInterval> | null = null;

	async send(card: Card, box: Box, at: number): Promise<boolean> {
		const went = await request(
			'/api/tv/open',
			json({ kind: card.kind, id: card.id, box: box.id, lang: i18n.locale, at: at > 10 ? at : null }),
			{ on: { 503: () => toasts.error(t('cast.tvAsleep')) } }
		);
		if (!went) return false;
		this.follow({
			box: { id: box.id, name: box.name },
			kind: card.kind,
			id: card.id,
			title: card.title,
			subtitle: card.subtitle ? String(card.subtitle) : '',
			cover: card.image ?? null
		});
		this.position = at;
		this.sent = Date.now();
		return true;
	}

	/** A film already on a television when this screen opens — sent from here
	 *  before the page was reloaded, or from anywhere else in the house. */
	async adopt() {
		for (const box of await televisions()) {
			const now = await request<TvNow>(`/api/tv/now?box=${box.id}`, {}, { failed: () => {} });
			if (!now || now.transport === 'idle' || !now.kind || !FILMS.has(now.kind) || now.item_id === null)
				continue;
			this.follow({
				box: { id: box.id, name: box.name },
				kind: now.kind,
				id: now.item_id,
				title: now.title,
				subtitle: now.artist,
				cover: now.cover_url
			});
			this.take(now);
			return;
		}
	}

	toggle() {
		void this.control('play_pause');
		this.playing = !this.playing;
		this.held = Date.now();
	}

	seek(to: number) {
		const at = Math.max(0, Math.min(to, this.duration || to));
		void this.control('seek', at);
		this.position = at;
		this.held = Date.now();
	}

	async stop() {
		await this.control('stop');
		this.let();
	}

	private async control(command: string, at?: number) {
		const on = this.on;
		if (!on) return;
		await request('/api/tv/control', json({ command, box: on.box.id, at: at ?? null }), {
			on: { 503: () => this.lost() }
		});
	}

	private follow(on: OnTv) {
		this.stopTimers();
		this.on = on;
		this.quiet = 0;
		this.started = false;
		this.playing = false;
		this.duration = 0;
		this.poller = setInterval(() => void this.poll(), POLL_MS);
		this.clock = setInterval(() => {
			if (this.playing && this.started) this.position += 1;
		}, 1000);
	}

	private async poll() {
		const on = this.on;
		if (!on) return;
		const now = await request<TvNow>(`/api/tv/now?box=${on.box.id}`, {}, { failed: () => {} });
		if (this.on !== on || !now) return;
		const kind = now.transport !== 'idle' && now.kind && FILMS.has(now.kind) ? now.kind : null;
		if (!this.started) {
			if (kind === on.kind && now.item_id === on.id) this.take(now);
			else if (Date.now() - this.sent > TAKE_MS) {
				toasts.error(t('cast.tvRefused', { name: on.box.name }));
				this.let();
			}
			return;
		}
		if (!kind || now.item_id === null) {
			this.quiet ||= Date.now();
			this.playing = false;
			if (!now.listening || Date.now() - this.quiet > QUIET_MS) this.let();
			return;
		}
		this.quiet = 0;
		// the next episode, put on by the television itself
		if (kind !== on.kind || now.item_id !== on.id)
			this.on = { ...on, kind, id: now.item_id, title: now.title, subtitle: now.artist, cover: now.cover_url };
		this.take(now);
	}

	private take(now: TvNow) {
		this.started = true;
		this.duration = now.duration ?? 0;
		if (Date.now() - this.held < HOLD_MS) return;
		this.playing = now.transport === 'playing';
		this.position = now.position ?? 0;
	}

	private lost() {
		toasts.error(t('cast.tvAsleep'));
		this.let();
	}

	private let() {
		this.stopTimers();
		this.on = null;
		this.started = false;
		this.playing = false;
		this.position = 0;
		this.duration = 0;
	}

	private stopTimers() {
		if (this.poller) clearInterval(this.poller);
		if (this.clock) clearInterval(this.clock);
		this.poller = this.clock = null;
	}
}

export const tvFilm = new TvFilm();
