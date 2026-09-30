// Where the sound comes out. The queue owns what plays; this owns which box
// plays it — this screen, the DAC for stereo, the receiver for anything with
// more channels — and keeps the bar honest about a device it is not itself
// driving, by asking after it on a slow heartbeat.

import { t } from '$lib/i18n';
import { forget, json, keep, recall, request, toasts, withLang } from '$lib/kit';
import { hasEngine, queue, type QueueTrack } from '$lib/keep/queue.svelte';
import { film } from '$lib/keep/film.svelte';
import { shown, type Show } from '$lib/keep/tvPhoto.svelte';
import { goto } from '$app/navigation';
import type { Card } from '$lib/keep/types';
import { spoken } from '$lib/say/episode';
import { sleeve } from '$lib/keep/sleeve.svelte';
import { surface } from '$lib/keep/surface.svelte';
import { onBox } from '$lib/tv/bridge';
import { SKIP_S } from '$lib/tvui/keys';

export type OutputId = 'browser' | 'stereo' | 'multi';
export type Output = { id: OutputId; entity?: string; name?: string };

type CastReport = {
	transport: string;
	title: string;
	artist: string;
	album: string;
	source: string | null;
	position: number | null;
	duration: number | null;
	index: number | null;
	volume: number | null;
	mute: boolean | null;
	track_id?: number | null;
	release_id?: number | null;
	cover_url?: string | null;
};

const STORED = 'opus-player-output';
// the device a television is showing, for the page that replaces it to go on showing
const FOLLOWED = 'opus-player-following';

const asleep = () => toasts.error(t('cast.tvAsleep'));
const POLL_MS = 2500;

function payload(tracks: QueueTrack[]) {
	return tracks.map((t) => ({
		id: t.id,
		title: t.title,
		artist: t.artist,
		album: t.album,
		cover_url: t.cover_url,
		codec: t.codec ?? null,
		url: t.url ?? null
	}));
}

/** Every question to the inbox says where the box is plugged in, so a box
 *  carried to another screen is known there by its next one. */
function asking(where: Record<string, string>): URLSearchParams {
	const asked = new URLSearchParams(where);
	const plugged = onBox((box) => box.plugged?.() ?? '', () => {});
	if (plugged) asked.set('sink', plugged);
	return asked;
}

class CastState {
	outputs = $state<Output[]>([{ id: 'browser' }]);
	/** what the person asked for; 'auto' means the track decides */
	choice = $state<OutputId | 'auto'>('auto');
	/** what the current queue actually plays on */
	active = $state<OutputId>('browser');
	transport = $state('stopped');
	position = $state(0);
	/** the last position the device reported, to tell a moving clock from a
	 *  standing one */
	duration = $state(0);
	volume = $state<number | null>(null);
	mute = $state(false);
	/** Track id reported by the output, used to reject a transient next-song
	 * report until the queue has moved to that same item. */
	trackId = $state<number | null>(null);
	/** what the device itself says is on — the truth for a queue it advances */
	title = $state('');
	artist = $state('');
	album = $state('');

	private timer: ReturnType<typeof setInterval> | null = null;

	get casting(): boolean {
		return this.active !== 'browser';
	}

	/** Asked before each wait for an order; false once the page is being
	 *  replaced. A television that slept through a deploy wakes on the order
	 *  that woke it, and the build that takes the order is the one that plays it. */
	fresh: () => Promise<boolean> = async () => true;

	/** This screen is driving the television rather than playing anything: what
	 *  the keys do here happens over there, which is worth saying out loud. */
	get remote(): boolean {
		return this.active === 'multi' &&
			this.outputs.find((o) => o.id === 'multi')?.entity === 'tv';
	}

	get playing(): boolean {
		return this.transport === 'playing' || this.transport === 'buffering';
	}

	async load() {
		const kept = recall(STORED);
		if (kept === 'auto' || kept === 'browser' || kept === 'stereo' || kept === 'multi')
			this.choice = kept;
		const got = await request<{ outputs: Output[] }>('/api/cast/outputs');
		if (got) this.outputs = got.outputs;
		queue.autocast = () => void this.begin();
		if (surface.current === 'tv') {
			this.reattach();
			this.receive();
			// switched on in the middle of a record: nothing was ordered while
			// this screen was dark, so it has to go and look
			if (!queue.current && !(await this.refollow())) await this.adopt();
		} else await this.adopt();
	}

	/** A new build replaced the page while it was showing a device, and the
	 *  device plays on: the face comes back with it. */
	private async refollow(): Promise<boolean> {
		const kept = recall(FOLLOWED);
		if (!kept) return false;
		forget(FOLLOWED);
		const was = JSON.parse(kept) as { where: OutputId; tracks: QueueTrack[]; start: number };
		const got = await request<CastReport>(`/api/cast/state?output=${was.where}`, {}, { failed: () => {} });
		if (got?.transport !== 'playing' && got?.transport !== 'paused') return false;
		this.follow(was.where, was.tracks, was.start);
		return true;
	}

	/** The box kept playing while the page went away and came back — a new build
	 *  reloads the screen and the engine, which is not the page, plays on. What
	 *  was on is remembered; where it had got to is asked of the engine itself. */
	private reattach() {
		if (!hasEngine() || queue.current) return;
		const kept = queue.kept();
		if (!kept) return;
		const said = onBox(
			(box) => JSON.parse(box.state()) as { position?: number; playing?: boolean; ended?: boolean }
		);
		if (!said?.playing || said.ended) return;
		queue.resume(kept.tracks, kept.index, said.position ?? 0);
	}

	/** The television's half of the mailbox: wait for orders from the other
	 *  screens, play them through this session's own engine, and keep telling
	 *  the server what is on so those screens can mirror it. */
	private receiving = false;
	private receive() {
		if (this.receiving) return;
		this.receiving = true;
		// nothing acted on yet: the first answer only says where the count stands
		let where: Record<string, string> = {};
		const listen = async () => {
			for (;;) {
				if (!(await this.fresh())) return;
				const said = await request<{
					boot: string;
					seq: number;
					order: {
						tracks: QueueTrack[];
						start: number;
						watch?: OutputId | null;
						/** a place the house sent this television to */
						go?: string;
						/** a film the house asked it to play */
						film?: Card;
						/** where the screen that sent it had got to */
						at?: number;
						/** whose place in it this is, when a phone sent it */
						sent?: string;
						/** a photograph a phone is showing here, or null to put it away */
						photo?: string | null;
						/** photographs one after another the house asked for */
						show?: Show;
						/** what was being watched here, put on again */
						resume?: boolean;
					} | null;
					control: { command: string; at?: number } | null;
				}>(`/api/tv/inbox?${asking(where)}`, {}, { failed: () => {} });
				// a mailbox that did not answer is asked again, not reported: the
				// door itself says when this screen has been taken back
				if (!said) {
					await new Promise((r) => setTimeout(r, 5000));
					continue;
				}
				where = { seq: String(said.seq), boot: said.boot };
				if (said.order && 'photo' in said.order) {
					if (said.order.photo) {
						film.current?.stop();
						void shown.open(said.order.photo);
					} else shown.close();
				} else if (said.order?.show) {
					film.current?.stop();
					shown.play(said.order.show);
				} else if (said.order?.resume) {
					shown.close();
					void this.resume();
				} else if (said.order?.go) void goto(said.order.go);
				else if (said.order?.film) {
					shown.close();
					film.ask(said.order.film, said.order.at, said.order.sent);
				}
				else if (said.order?.watch)
					this.follow(said.order.watch, said.order.tracks, said.order.start);
				else if (said.order) {
					this.watching = false;
					queue.play(said.order.tracks, said.order.start);
				}
				if (said.control) this.obey(said.control.command, said.control.at);
			}
		};
		void listen();
		// The remote's media keys, handed over by the wrapper's media session:
		// play and pause the engine answers by itself, and what is left — next,
		// previous, stop — means something only this page knows.
		window.opusTvKey = (command: string) => this.obey(command);
		// whether the last thing told was something on: nothing on is said once,
		// the moment it stops, rather than left for the server to notice by the
		// report going quiet
		let said = false;
		setInterval(() => {
			const photo = shown.photo?.id ?? null;
			const on = film.current;
			if (on) {
				said = true;
				void this.report({
					photo,
					kind: on.kind,
					item_id: on.id,
					playing: on.playing(),
					title: on.title,
					artist: on.subtitle,
					album: '',
					position: on.position(),
					duration: on.duration(),
					cover_url: on.cover
				});
				return;
			}
			// a screen that is only showing somebody else's record must not
			// report it as its own: the other screens would then mirror this
			// echo instead of the device that is actually playing
			if (!queue.current || this.watching) {
				if (said || photo) void this.report({ kind: 'none', playing: false, photo });
				said = photo !== null;
				return;
			}
			said = true;
			void this.report({
				photo,
				// a stream somebody else keeps alive is a station, whoever put it on
				kind: queue.current.url ? 'station' : 'track',
				item_id: queue.current.id,
				playing: queue.playing,
				title: queue.current.title,
				artist: queue.current.artist,
				album: queue.current.album,
				position: queue.position,
				duration: queue.current.duration_s,
				index: queue.index,
				track_id: queue.current.id,
				release_id: queue.current.release_id ?? null,
				cover_url: queue.current.cover_url
			});
		}, 2000);
	}

	/** A heartbeat: one that does not arrive is followed by the next, and a
	 *  screen the backend stopped recognising is sent back to the door by the
	 *  request layer itself. */
	/** What was being watched here, put on again: the first of this profile's
	 *  continue row, the same card the row would have opened. */
	private async resume() {
		const said = await request<{ rows: { key: string; cards: Card[] }[] }>(
			withLang('/api/home'),
			{},
			{ failed: () => {} }
		);
		if (!said) return;
		const card = said.rows.find((row) => row.key === 'continue')?.cards[0];
		if (card) film.ask(spoken(card));
		else toasts.info(t('cast.nothingToResume'));
	}

	private report(said: Record<string, unknown>) {
		return request('/api/tv/state', json(said), { failed: () => {} });
	}

	/** The record is playing on a device in the house and this screen is its
	 *  face: show it, follow it, play nothing. The engine is stopped rather
	 *  than left running — the television was told to hand the sound over. */
	private watching = false;
	/** showing a device rather than playing: a reload stops nothing */
	get following(): boolean {
		return this.watching;
	}
	private follow(where: OutputId, tracks: QueueTrack[], start: number) {
		if (hasEngine()) onBox((box) => box.stop());
		this.watching = true;
		keep(FOLLOWED, JSON.stringify({ where, tracks, start }));
		queue.resume(tracks, start, 0);
		this.active = where;
		this.transport = 'playing';
		this.startPolling();
		sleeve.show();
	}

	/** The record being watched is over, said rather than guessed. The house
	 *  reports this streamer's transport so sparsely that it reads as stopped
	 *  the whole way through a record — a screen that let go on that telemetry
	 *  put the album up and snatched it away again. So the screen holds what it
	 *  was given until somebody says otherwise. */
	private letGo() {
		this.watching = false;
		forget(FOLLOWED);
		this.stopPolling();
		this.active = 'browser';
		this.transport = 'stopped';
		sleeve.hide();
		queue.clear();
	}

	/** An order — from another screen in the house, from the box's media session,
	 *  or from the remote's own key where nothing on the box is holding it. */
	obey(command: string, at?: number) {
		// photographs over everything are what a stop puts away first
		if (command === 'stop' && (shown.photo || shown.slides)) {
			shown.close();
			return;
		}
		// a film on the screen is what an order is about while it is there
		const on = film.current;
		if (on) {
			const playing = on.playing();
			if (command === 'play_pause' || (command === 'play' && !playing) || (command === 'pause' && playing))
				on.toggle();
			else if (command === 'seek' && at !== undefined) on.seek(at);
			else if (command === 'next') on.step(1);
			else if (command === 'next_episode') on.episode();
			else if (command === 'previous') on.step(-1);
			else if (command === 'stop') on.stop();
			else if (command === 'forward' || command === 'back')
				on.seek(on.position() + (command === 'forward' ? SKIP_S : -SKIP_S));
			return;
		}
		if (command === 'stop' && this.watching) {
			this.letGo();
			return;
		}
		if (command === 'play') queue.playing = true;
		else if (command === 'pause') queue.playing = false;
		else if (command === 'play_pause') queue.playing = !queue.playing;
		else if (command === 'next') {
			if (this.casting) void this.next();
			else queue.next();
		}
		else if (command === 'previous') {
			if (this.casting) void this.previous();
			else queue.jump(Math.max(0, queue.index - 1));
		}
		else if (command === 'stop') void this.silence();
		else if ((command === 'forward' || command === 'back') && !this.casting && hasEngine()) {
			// only where this box holds the record's clock: a device elsewhere in the
			// house is not sought on from the bar either
			const to = Math.max(0, queue.position + (command === 'forward' ? SKIP_S : -SKIP_S));
			onBox((box) => box.seek(to));
			queue.position = to;
		}
	}

	/** A record put on from another screen is still on, and this screen should
	 *  say so. Both places are asked, the television first: it is another face
	 *  of this player and the likelier thing to be carrying a queue, and it
	 *  reports enough about the song for the sleeve to show its own cover and
	 *  its own words rather than a title standing on its own. */
	private async adopt() {
		if (queue.current) return;
		// the television is the multichannel output; asking after that one from
		// there is asking after itself, and its own engine has already answered
		const look = surface.current === 'tv' ? (['stereo'] as const) : (['multi', 'stereo'] as const);
		for (const where of look) {
			if (!this.configured(where)) continue;
			// what the house is doing is looked at, not waited on: a device that
			// does not answer is a device with nothing of ours on it
			const got = await request<CastReport>(`/api/cast/state?output=${where}`, {}, {
				failed: () => {}
			});
			if (!got) continue;
			if (got.source !== 'library') continue;
			if (got.transport !== 'playing' && got.transport !== 'paused') continue;
			this.active = where;
			this.transport = got.transport;
			this.position = got.position ?? 0;
			this.duration = got.duration ?? 0;
			this.title = got.title;
			this.artist = got.artist ?? '';
			this.album = got.album ?? '';
			this.trackId = got.track_id ?? null;
			queue.tracks = [{
				id: got.track_id ?? -1,
				position: 1,
				title: got.title,
				artist: got.artist ?? '',
				album: got.album ?? '',
				cover_url: got.cover_url ?? null,
				duration_s: got.duration ?? null,
				release_id: got.release_id ?? null
			}];
			queue.index = 0;
			queue.playing = got.transport === 'playing';
			// on the big screen this is somebody else's record, shown, not
			// played — the same standing as one that arrives by mailbox
			if (surface.current === 'tv') {
				this.watching = true;
				sleeve.show();
			}
			this.startPolling();
			return;
		}
	}

	private configured(id: OutputId): boolean {
		return this.outputs.some((o) => o.id === id);
	}

	/** the output this queue should play on: the person's word first, then the
	 *  channel count — stereo to the DAC, more to the television whose HDMI is
	 *  the one road multichannel can take into the receiver */
	resolve(tracks: QueueTrack[]): OutputId {
		// ONE rule, for every screen: the record decides where it goes, not the
		// screen somebody happened to press play on. Stereo takes the DAC, more
		// than stereo takes the television's engine, whose HDMI is the one road
		// multichannel has into the receiver. A person who names an output means
		// it — asking for the television and being quietly sent to the DAC took
		// the picture away with the sound, because the receiver draws both off
		// the same input.
		//
		// The surface enters this exactly once, at the end: the television IS
		// the multichannel output, so 'multi' reaching it means itself. Having
		// that as a branch of its own is what made a two-channel record play out
		// of the television when the same record started from a laptop went to
		// the DAC — the same question answered twice, differently.
		const wide = tracks.some((t) => (t.channels ?? 0) > 2);
		const roads: OutputId[] =
			this.choice === 'auto' ? (wide ? ['multi', 'stereo'] : ['stereo']) : [this.choice];
		const want = roads.find((o) => o !== 'browser' && this.configured(o)) ?? 'browser';
		return surface.current === 'tv' && want === 'multi' ? 'browser' : want;
	}


	/** queue.play happened: aim it. Called through queue.autocast so the pages
	 *  keep saying only queue.play(...) no matter where the sound goes. */
	async begin() {
		const to = this.resolve(queue.tracks);
		this.active = to;
		if (to === 'browser') {
			this.stopPolling();
			return;
		}
		queue.startAt = 0; // a renderer starts a track at its start
		const went = await request(
			'/api/cast/play',
			json({ output: to, tracks: payload(queue.tracks), start: queue.index }),
			{ on: { 503: asleep } }
		);
		// The device would not take it — the amplifier is off, the television is
		// not listening, the house did not answer. A screen that never took the
		// record is not one to mirror, so this stops following it; but somebody
		// pressed play and something has to play. It plays here, and the refusal
		// has already said itself in a toast.
		if (!went) {
			this.active = 'browser';
			this.stopPolling();
			queue.startAt = 0;
			queue.playing = true;
			return;
		}
		this.startPolling();
	}

	/** the person picked an output while something is on: carry the record over */
	async choose(choice: OutputId | 'auto') {
		this.choice = choice;
		keep(STORED, choice);
		if (!queue.current) return;
		const to = this.resolve(queue.tracks);
		if (to === this.active) return;
		if (this.casting) await this.control('stop');
		if (to === 'browser') {
			// back onto this screen, from where the device left off
			this.active = 'browser';
			this.stopPolling();
			queue.startAt = this.position;
			queue.playing = true;
		} else {
			await this.begin();
		}
	}

	async control(command: string) {
		if (!this.casting) return;
		await request('/api/cast/control', json({ output: this.active, command }), {
			on: { 503: asleep }
		});
	}

	// both cast outputs own their queue — the DAC's MPD and the television's
	// engine advance themselves; the keys only ask
	async next() {
		// Do not move the face of the player before the output confirms it. The
		// receiver/MPD can take a moment to advance; changing the index here made
		// Home show the next album while the previous track was still playing.
		await this.control('next');
	}

	async previous() {
		// The next state poll supplies the device's authoritative index.
		await this.control('previous');
	}

	async toggle() {
		await this.control(this.playing ? 'pause' : 'play');
		// the poll confirms; flip now so the key answers the finger
		this.transport = this.playing ? 'paused' : 'playing';
	}

	async stop() {
		await this.control('stop');
		this.stopPolling();
		this.active = 'browser';
		this.transport = 'stopped';
		this.position = 0;
	}

	/** Stop, wherever the sound is actually coming from, and let the record go.
	 *
	 *  There were two ideas of stopping. The bar's key knew to stop the device
	 *  or the box's engine before emptying the queue; the remote's stop key only
	 *  emptied it — so the screen went quiet, the bar went away, and the box
	 *  played the record out to the end with nothing left to stop it with. */
	async silence() {
		if (this.casting) await this.stop();
		else if (hasEngine()) onBox((box) => box.stop());
		queue.clear();
	}

	async setVolume(command: 'up' | 'down' | 'mute') {
		await request('/api/cast/volume', json({ command }));
	}

	private startPolling() {
		this.stopPolling();
		this.timer = setInterval(() => void this.poll(), POLL_MS);
	}

	private stopPolling() {
		if (this.timer) clearInterval(this.timer);
		this.timer = null;
	}

	private polling = false;

	private async poll() {
		if (!this.casting || !queue.current) {
			this.stopPolling();
			return;
		}
		// a device slower to answer than the beat is asked once, not over itself
		if (this.polling) return;
		this.polling = true;
		// a missed heartbeat is not a verdict
		const got = await request<CastReport>(`/api/cast/state?output=${this.active}`, {}, {
			failed: () => {}
		});
		this.polling = false;
		if (!got) return;
		// The house has put something else on — the radio, most often, or a
		// record started from its own surfaces. What is on the screen has to be
		// what is playing: the last record's sleeve, its songs and its words
		// standing under a station's name is a lie made of two truths.
		// …unless what is on IS a station this player put on: then the device's
		// title is the song playing on it, not a different record, and replacing
		// the station with it would lose the station.
		if (got.source && got.source !== 'library' && got.title && !queue.current?.url &&
			(queue.tracks.length !== 1 || queue.current?.title !== got.title)) {
			queue.tracks = [{
				id: -1,
				position: 1,
				title: got.title,
				artist: got.artist ?? '',
				album: got.album ?? '',
				cover_url: got.cover_url ?? null,
				duration_s: got.duration ?? null,
				release_id: null,
				live: true
			}];
			queue.index = 0;
		}
		this.transport = got.transport;
		this.position = got.position ?? 0;
		this.duration = got.duration ?? 0;
		this.volume = got.volume;
		this.mute = got.mute ?? false;
		this.title = got.title ?? '';
		this.artist = got.artist ?? '';
		this.album = got.album ?? '';
		this.trackId = got.track_id ?? null;
		queue.position = this.position;
		// the device advances its own queue; the bar follows it
		if (got.index != null && got.index !== queue.index &&
			got.index >= 0 && got.index < queue.tracks.length)
			queue.index = got.index;
	}
}

export const cast = new CastState();
