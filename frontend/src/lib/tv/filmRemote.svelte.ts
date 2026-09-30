import { surface } from '$lib/keep/surface.svelte';
import { SKIP_S } from '$lib/tvui/keys';

type Film = {
	stage: () => HTMLElement | null;
	ready: () => boolean;
	position: () => number;
	seek: (to: number) => void;
	toggle: () => void;
	onward: () => boolean;
	scene: (at: number, step: number) => number | null;
	hideInfo: () => boolean;
	stir: () => void;
};

/** A film on a television, driven by a remote.
 *
 * On a television the bar is somewhere you go, not something the arrows are
 * always inside. With it away, left and right are the film. With it up, they
 * are the controls along it — until OK is pressed on the position, which hands
 * the arrows back to the film without leaving the bar. */
export class FilmRemote {
	inBar = $state(false);
	/** A native select answers the remote by opening itself and swallowing the
	 *  key that got there, so on a television the tracks are our own list. */
	menu = $state<'audio' | 'subs' | 'cast' | null>(null);
	scrubbing = $state(false);
	/** Moving through a film with the bar away is moving blind. The bar shows
	 *  itself for the length of the move without taking the remote — the arrows
	 *  are still the film, they just stop being a guess. */
	peek = $state(false);

	#film: Film;
	#peekTimer: ReturnType<typeof setTimeout> | null = null;
	#barTimer: ReturnType<typeof setTimeout> | null = null;

	constructor(film: Film) {
		this.#film = film;
	}

	glance() {
		this.peek = true;
		if (this.#peekTimer) clearTimeout(this.#peekTimer);
		this.#peekTimer = setTimeout(() => (this.peek = false), 2500);
	}

	openMenu(which: 'audio' | 'subs' | 'cast') {
		this.menu = which;
		queueMicrotask(() => this.#film.stage()?.querySelector<HTMLElement>('[data-choice]')?.focus());
	}

	closeMenu() {
		const back = this.menu;
		this.menu = null;
		queueMicrotask(() =>
			this.#film.stage()?.querySelector<HTMLElement>(`[data-menu="${back}"]`)?.focus()
		);
	}

	#alongMenu(step: number) {
		const items = Array.from(this.#film.stage()?.querySelectorAll<HTMLElement>('[data-choice]') ?? []);
		const at = items.indexOf(document.activeElement as HTMLElement);
		items[Math.min(items.length - 1, Math.max(0, at + step))]?.focus();
	}

	/** The controls, and not the position among them. A remote walking the bar
	 *  wants play, sound, subtitles — the position is a line, and a line between
	 *  the play button and the languages is a stop nobody meant to make and a
	 *  trap once OK is pressed on it. It has its own way in, above. */
	#barControls(): HTMLElement[] {
		return Array.from(this.#film.stage()?.querySelectorAll<HTMLElement>('[data-control]') ?? []);
	}

	#scrubber(): HTMLElement | null {
		return this.#film.stage()?.querySelector<HTMLElement>('[data-position]') ?? null;
	}

	/** The bar is a visit, not a state. It leaves by itself a few seconds after
	 *  the last press, the way it would if a hand had stopped moving — a list
	 *  being read is the one thing that holds it. */
	#keepBar() {
		if (this.#barTimer) clearTimeout(this.#barTimer);
		this.#barTimer = setTimeout(() => {
			if (!this.menu) this.leaveBar();
		}, 4000);
	}

	#enterBar() {
		this.inBar = true;
		this.#film.stir();
		this.#keepBar();
		queueMicrotask(() => this.#barControls()[0]?.focus());
	}

	leaveBar() {
		if (this.#barTimer) clearTimeout(this.#barTimer);
		this.#barTimer = null;
		this.inBar = false;
		this.#film.stage()?.focus();
	}

	/** Left and right along the bar, moved by us rather than by the browser: a
	 *  closed select answers an arrow key by changing its own value, so letting
	 *  these through would swap the audio track on the way past it. */
	#alongBar(step: number) {
		const controls = this.#barControls();
		const at = controls.indexOf(document.activeElement as HTMLElement);
		controls[Math.min(controls.length - 1, Math.max(0, at + step))]?.focus();
	}

	onkey = (event: KeyboardEvent) => {
		const film = this.#film;
		if (!surface.isTv || event.defaultPrevented || !film.ready()) return;
		if (!this.menu && (event.key === 'Escape' || event.key === 'ArrowLeft') && film.hideInfo()) {
			event.preventDefault();
			return;
		}
		if (this.menu) {
			// The list owns every arrow while it is open. Left to the page's own
			// spatial move, down from the first track lands on the position bar
			// behind it — a thin line that takes the focus and is not a language.
			if (event.key === 'Escape' || event.key === 'ArrowLeft') {
				this.closeMenu();
				event.preventDefault();
			} else if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
				this.#alongMenu(event.key === 'ArrowDown' ? 1 : -1);
				event.preventDefault();
			} else if (event.key === 'ArrowRight') {
				event.preventDefault();
			}
			return;
		}
		if (!this.inBar) {
			if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
				film.seek(film.position() + (event.key === 'ArrowRight' ? SKIP_S : -SKIP_S));
				this.glance();
				event.preventDefault();
			} else if (event.key === 'ArrowDown') {
				this.#enterBar();
				event.preventDefault();
			} else if (event.key === 'Enter' || event.key === ' ') {
				if (!film.onward()) film.toggle();
				event.preventDefault();
			}
			return;
		}
		this.#keepBar();
		// Up from the controls is the position, and on the position the arrows go
		// back to being the film while the bar stays up and shows where they are
		// taking it. Down comes back to the controls; up again puts the bar away.
		if (this.scrubbing) {
			if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
				// On the position the arrows move by scene where a film has them,
				// and by ten seconds where it does not. The fine step is still
				// there, with the bar away — coarse and fine, one in each place.
				const step = event.key === 'ArrowRight' ? 1 : -1;
				const mark = film.scene(film.position(), step);
				film.seek(mark ?? film.position() + step * SKIP_S);
			} else if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
				this.scrubbing = false;
				this.#barControls()[0]?.focus();
			} else if (event.key === 'ArrowUp' || event.key === 'Escape') {
				this.scrubbing = false;
				this.leaveBar();
			}
			event.preventDefault();
			return;
		}
		if (event.key === 'ArrowUp') {
			this.scrubbing = true;
			this.#scrubber()?.focus();
			event.preventDefault();
		} else if (event.key === 'ArrowDown' || event.key === 'Escape') {
			this.leaveBar();
			event.preventDefault();
		} else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
			this.#alongBar(event.key === 'ArrowRight' ? 1 : -1);
			event.preventDefault();
		}
	};
}
