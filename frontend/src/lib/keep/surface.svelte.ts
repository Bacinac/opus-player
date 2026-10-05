// Which surface this is running on, and therefore how the app is shaped.
//
// Not sniffed from the user-agent, which lies and goes stale. Asked of the
// device itself: does it have a fine pointer, can it hover, how wide is it. A
// laptop plugged into a television is a television, and says so by being told —
// the override is a first-class answer, not a debug flag.

import { forget, keep, recall } from '$lib/kit';

export type Surface = 'tv' | 'desktop' | 'tablet' | 'mobile';

export const SURFACES: Surface[] = ['tv', 'desktop', 'tablet', 'mobile'];

const OVERRIDE_KEY = 'opus.player.surface';

/** What the Android wrapper appends to its user agent. Kept in step with
 *  SAYS_TV in android/.../PlayerActivity.kt, which is the only thing that
 *  writes it. */
const SAYS_TV = 'OPUSPlayer/tv';

function detect(): Surface {
	if (typeof window === 'undefined') return 'desktop';

	// Ours says it in the user agent, which is the only place that survives
	// everything: the address is lost when the WebView restores its own state
	// after the box restarts, and storage is lost with the process. It was said
	// in the address alone, so every reboot came back looking like a tablet.
	if (navigator.userAgent.includes(SAYS_TV)) return 'tv';

	const coarse = window.matchMedia('(pointer: coarse)').matches;
	const noHover = window.matchMedia('(hover: none)').matches;
	const w = window.innerWidth;

	// A big screen you cannot point at is a television — but this is a guess and
	// not a good one. The Shield hands its page 960 by 540, under any threshold
	// that does not also catch a tablet, which is exactly why the wrapper says
	// so outright above rather than leaving it to this.
	if (coarse && noHover && w >= 1280) return 'tv';
	if (coarse || noHover) return w >= 700 ? 'tablet' : 'mobile';
	return w < 700 ? 'mobile' : 'desktop';
}

class SurfaceState {
	current = $state<Surface>('desktop');
	forced = $state<Surface | null>(null);

	private started = false;

	init() {
		if (this.started) return;
		this.started = true;
		const update = () => {
			if (!this.forced) this.current = detect();
		};
		window.addEventListener('resize', update);
		window.matchMedia('(pointer: coarse)').addEventListener('change', update);
		window.matchMedia('(hover: none)').addEventListener('change', update);
		// an address can say it outright: the laptop plugged into a television
		// is the case no capability query can see
		const asked = new URLSearchParams(window.location.search).get('surface') as Surface | null;
		if (asked && SURFACES.includes(asked)) {
			this.force(asked);
			return;
		}
		const stored = recall(OVERRIDE_KEY) as Surface | null;
		if (stored && SURFACES.includes(stored)) {
			this.forced = stored;
			this.current = stored;
			return;
		}
		this.current = detect();
	}

	force(surface: Surface | null) {
		this.forced = surface;
		if (surface) {
			keep(OVERRIDE_KEY, surface);
			this.current = surface;
		} else {
			forget(OVERRIDE_KEY);
			this.current = detect();
		}
	}

	get isTv() {
		return this.current === 'tv';
	}
	get isMobile() {
		return this.current === 'mobile';
	}
	get touch() {
		return this.current === 'mobile' || this.current === 'tablet';
	}
}

export const surface = new SurfaceState();
