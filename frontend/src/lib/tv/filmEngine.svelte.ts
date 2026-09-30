import { t } from '$lib/i18n';
import { request, withLang } from '$lib/kit';
import { asked, hears, here } from '$lib/ask/ability';
import type { Card, EngineTrack, Plan } from '$lib/keep/types';
import { onBox } from '$lib/tv/bridge';

type Refused = { failed: (detail: string) => void };

export class FilmEngine {
	// When the box plays for itself the picture is drawn behind this page and
	// everything above it stays exactly what it was — one transport, not two.
	on = $state(false);
	at = $state(0);
	// A box that cannot render the film's sound is handed a stream the server
	// rebuilt around it, and a rebuilt stream cannot be sought inside: it is
	// started again at the new place, and its clock counts from there.
	rebuilt = $state(false);
	from = $state(0);
	length = $state(0);
	playing = $state(false);
	audio = $state<EngineTrack[]>([]);
	text = $state<EngineTrack[]>([]);
	decoder = $state('');
	dropped = $state(0);
	picture = $state('');

	#query = '';
	#pass = '';
	#prefix = '';
	#failed: (detail: string) => void;
	#said = '';

	/** `failed` is where a refusal is said: while a film is on the engine the
	 *  page is hidden behind it, and a toast would be said to nobody. */
	constructor(failed: (detail: string) => void) {
		this.#failed = failed;
	}

	#ask(asking: (box: NonNullable<Window['opusTv']>) => void): boolean {
		return onBox((box) => {
			asking(box);
			return true;
		}, this.#failed) ?? false;
	}

	async plan(card: Card, audio: number, refused: Refused): Promise<{ plan: Plan; audio: number } | null> {
		const base = `/api/play/${card.kind}/${card.id}`;
		const [pass, native] = await Promise.all([
			request<{ prefix: string; ticket: string }>(`${base}/ticket`, {}, refused),
			request<Plan>(withLang(`${base}/plan?${asked(here(), { native: true, canDecode: true })}`), {}, refused)
		]);
		if (!pass || !native) return null;
		this.#prefix = pass.prefix;
		this.#pass = `ticket=${encodeURIComponent(pass.ticket)}`;
		const place = here();
		const track = native.audio.find((a) => a.index === audio) ?? native.audio[0];
		const video = onBox((box) => box.canVideo(
			native.source.video_codec ?? '', native.source.width ?? 0, native.source.height ?? 0
		), this.#failed);
		const hasVideo = video === true;
		// Sound is the one thing a box can be unable to render while decoding the
		// picture perfectly. What it CAN render travels with the request, so the
		// server rebuilds around the box rather than around an assumption: a 7.1
		// track came out of the room as a pair of speakers for as long as nobody
		// said what else this box would accept.
		const hasAudio = hears(place, track?.codec ?? '', track?.channels ?? 0);
		this.rebuilt = !hasVideo || !hasAudio;
		const chosen = track?.index ?? 0;
		this.#query = asked(place, {
			canDecode: hasVideo,
			audio: chosen,
			native: true,
			rebuildAudio: !hasAudio
		});
		const made = this.rebuilt
			? await request<Plan>(withLang(`${base}/plan?${this.#query}`), {}, refused)
			: native;
		return made ? { plan: made, audio: chosen } : null;
	}

	start(plan: Plan, at: number): boolean {
		const from = this.rebuilt ? Math.floor(at) : 0;
		const rebase = this.rebuilt ? `&t=${from}${plan.mode === 'remux' ? '&snap=1' : ''}` : '';
		// The catalogue went and found the Croatian subtitle and put it beside the
		// file, so the tracks worth offering are not only the ones the container
		// happens to hold. The engine is told about both.
		const tracks = plan.subtitles.map((sub) => ({
			url: `${location.origin}${this.#prefix}subs/${sub.id}.vtt?${this.#pass}${rebase}`,
			lang: sub.lang,
			label: sub.lang.toUpperCase() + (sub.forced ? ` · ${t('play.forced')}` : '')
		}));
		this.from = from;
		this.at = this.rebuilt ? 0 : at;
		return this.#ask((box) =>
			box.play(
				`${location.origin}${this.#prefix}stream?${this.#query}&${this.#pass}${this.rebuilt ? `&t=${from}` : ''}`,
				this.rebuilt ? 0 : at,
				JSON.stringify(tracks),
				plan.preferred?.audio ?? '',
				plan.preferred?.subtitle ?? '',
				plan.source?.frame_rate ?? 0
			)
		);
	}

	seek(plan: Plan, at: number) {
		if (this.rebuilt) {
			this.start(plan, at);
			return;
		}
		if (this.#ask((box) => box.seek(at))) this.at = at;
	}

	chooseAudio(plan: Plan, index: number, at: number) {
		if (!this.rebuilt) {
			this.#ask((box) => box.chooseAudio(index));
			return;
		}
		this.#query = this.#query.replace(/audio=\d+/, `audio=${index}`);
		this.start(plan, at);
	}

	chooseText(index: number | null) {
		this.#ask((box) => box.chooseText(index ?? -1));
	}

	toggle() {
		this.#ask((box) => box.toggle());
	}

	stop() {
		this.#ask((box) => box.stop());
	}

	captionsUp(raised: boolean) {
		this.#ask((box) => box.captionsUp(raised));
	}

	/** What the engine is doing now, and whether the film has come to its end.
	 *  Asked on a clock rather than reported: it draws on a surface and knows
	 *  nothing about this page, and one crossing per look is cheaper than one
	 *  per field. */
	look(): boolean {
		const raw = onBox((box) => box.state(), this.#failed);
		if (!raw) return false;
		const now = JSON.parse(raw) as {
			position: number;
			duration: number;
			playing: boolean;
			ended: boolean;
			audio: EngineTrack[];
			text: EngineTrack[];
			decoder: string;
			dropped: number;
			picture: string;
			error?: string;
		};
		// no player behind the engine — between two films, or while the panel
		// changes mode — answers {}, and its undefined position is not a place
		// in the film to report to the server
		if (typeof now.position !== 'number') return false;
		this.at = now.position;
		this.length = now.duration;
		this.playing = now.playing;
		this.audio = now.audio ?? [];
		this.text = now.text ?? [];
		this.decoder = now.decoder ?? '';
		this.dropped = now.dropped ?? 0;
		this.picture = now.picture ?? '';
		if (now.error && now.error !== this.#said) this.#failed(t('play.engineFailed', { detail: now.error }));
		this.#said = now.error ?? '';
		return now.ended;
	}

	/** The page has to be see-through for the picture behind it to be seen, and
	 *  see-through means the library is still there — posters showing through a
	 *  film. What is not the film gets out of the way for as long as one is on.
	 *
	 *  Set here rather than in a stylesheet: the document's own background is
	 *  painted by rules that belong to every module, and a component reaching
	 *  past its own scope to argue with them is a specificity contest it can
	 *  quietly lose. It lost — an opaque body over a film that was playing the
	 *  whole time. */
	uncover(stage: HTMLElement | null): () => void {
		const body = document.body;
		const was = { background: body.style.background, overflow: body.style.overflow };
		body.style.background = 'transparent';
		body.style.overflow = 'hidden';
		const covered = [...body.children].map((node) => {
			const el = node as HTMLElement;
			const before = el.style.visibility;
			el.style.visibility = 'hidden';
			return [el, before] as const;
		});
		if (stage) stage.style.visibility = 'visible';
		return () => {
			body.style.background = was.background;
			body.style.overflow = was.overflow;
			for (const [el, before] of covered) el.style.visibility = before;
			if (stage) stage.style.visibility = '';
		};
	}
}
