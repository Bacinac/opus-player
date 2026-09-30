// A photograph a phone shows on a television while it goes through them. The
// phone's half holds which television it shows on and hands it every picture
// it moves to; the television's half opens the one it was handed in its own
// viewer and says which it shows, so a phone whose picture was put away over
// there stops handing it more.

import type { ComponentProps } from 'svelte';
import { t } from '$lib/i18n';
import { json, request, toasts } from '$lib/kit';
import { aboutOf } from '$lib/opus';
import type PhotoViewer from '$lib/opus/PhotoViewer.svelte';
import type { Box } from '$lib/keep/tvFilm.svelte';
import { onBox } from '$lib/tv/bridge';

export type Photo = ComponentProps<typeof PhotoViewer>['photo'];

const POLL_MS = 2500;
// a television may first be woken and have the player opened on it
const TAKE_MS = 60000;
// a picture nobody has moved on from in this long was left there, and the
// television goes back to its own screensaver rather than hold it forever
const LEFT_MS = 15 * 60 * 1000;
// photographs asked for aloud run for an evening's hour, then the box's own
// screensaver and its sleep take the screen back
const SHOW_MS = 60 * 60 * 1000;

class TvPhoto {
	on = $state.raw<{ id: number; name: string } | null>(null);
	/** the picture last handed over, which the bar shows */
	photo = $state.raw<Photo | null>(null);

	private sent: string | null = null;
	private going = false;
	private since = 0;
	private started = false;
	private poller: ReturnType<typeof setInterval> | null = null;

	start(box: Box) {
		this.stopPolling();
		this.sent = null;
		this.started = false;
		this.since = Date.now();
		this.on = { id: box.id, name: box.name };
		this.poller = setInterval(() => void this.poll(), POLL_MS);
	}

	/** The phone moved to another picture. Pictures passed faster than the house
	 *  answers are skipped, and what is sent goes in the order it was chosen. */
	show(photo: Photo) {
		if (!this.on) return;
		this.photo = photo;
		if (!this.going) void this.hand();
	}

	async stop() {
		const on = this.on;
		this.let();
		if (on) await request('/api/tv/photo', json({ id: null, box: on.id }));
	}

	private async hand() {
		this.going = true;
		while (this.on && this.photo && this.photo.id !== this.sent) {
			const id = this.photo.id;
			const went = await request('/api/tv/photo', json({ id, box: this.on.id }), {
				on: { 503: () => toasts.error(t('cast.tvAsleep')) }
			});
			if (!went) {
				this.let();
				break;
			}
			this.sent = id;
		}
		this.going = false;
	}

	private async poll() {
		const on = this.on;
		if (!on) return;
		const now = await request<{ photo: string | null }>(`/api/tv/now?box=${on.id}`, {}, { failed: () => {} });
		if (this.on !== on || !now) return;
		if (!this.started) {
			if (now.photo) this.started = true;
			else if (Date.now() - this.since > TAKE_MS) {
				toasts.error(t('cast.photoRefused', { name: on.name }));
				this.let();
			}
			return;
		}
		// put away over there: by the remote, by a film, by being left
		if (!now.photo) this.let();
	}

	private let() {
		this.stopPolling();
		this.on = null;
		this.photo = null;
		this.sent = null;
	}

	private stopPolling() {
		if (this.poller) clearInterval(this.poller);
		this.poller = null;
	}
}

export const tvPhoto = new TvPhoto();

export type Show = { person?: number; family?: boolean };

class Shown {
	/** the photograph a phone asked this television to show */
	photo = $state.raw<Photo | null>(null);
	/** the page showing photographs one after another that the house asked for */
	slides = $state<string | null>(null);

	private asked = 0;
	private left: ReturnType<typeof setTimeout> | null = null;

	async open(id: string) {
		const mine = ++this.asked;
		const got = await request<Photo>(aboutOf(id));
		if (mine !== this.asked || !got) return;
		this.slides = null;
		this.photo = got;
		this.hold(LEFT_MS);
	}

	play(show: Show) {
		this.asked++;
		this.photo = null;
		this.slides = show.person
			? `/show.html?person=${show.person}`
			: show.family
				? '/show.html?family'
				: '/show.html';
		this.hold(SHOW_MS);
	}

	close() {
		this.asked++;
		if (this.left) clearTimeout(this.left);
		this.left = null;
		if (!this.photo && !this.slides) return;
		this.photo = null;
		this.slides = null;
		onBox((box) => box.awake?.(false));
	}

	private hold(ms: number) {
		onBox((box) => box.awake?.(true));
		if (this.left) clearTimeout(this.left);
		this.left = setTimeout(() => this.close(), ms);
	}
}

export const shown = new Shown();
