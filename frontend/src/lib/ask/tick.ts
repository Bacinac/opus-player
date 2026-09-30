/* The clock, out loud.
 *
 * Asked of the browser rather than carried as files: four sounds of a few
 * milliseconds each are four requests, four caches and four things to get
 * wrong on a television with no speakers of its own. An oscillator is none of
 * that, and it is the same sound on every surface.
 *
 * Nothing is built until somebody has pressed something. A browser refuses to
 * make a sound before that and holds the context suspended if one is opened
 * early, so the game's own start is what opens it. */

let audio: AudioContext | null = null;

function context(): AudioContext | null {
	if (typeof window === 'undefined') return null;
	if (!audio) {
		const Sound = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
		if (!Sound) return null;
		audio = new Sound();
	}
	if (audio.state === 'suspended') void audio.resume();
	return audio;
}

/** One short sound. `hz` is what it is, `ms` how long, `gain` how much of it. */
function blip(hz: number, ms: number, gain = 0.06, shape: OscillatorType = 'sine') {
	const sound = context();
	if (!sound) return;
	const now = sound.currentTime;
	const tone = sound.createOscillator();
	const level = sound.createGain();
	tone.type = shape;
	tone.frequency.setValueAtTime(hz, now);
	// an envelope, not a switch: a square-edged blip clicks, and a click at
	// every second of a twenty-second question is a metronome nobody wants
	level.gain.setValueAtTime(0, now);
	level.gain.linearRampToValueAtTime(gain, now + 0.008);
	level.gain.exponentialRampToValueAtTime(0.0001, now + ms / 1000);
	tone.connect(level).connect(sound.destination);
	tone.start(now);
	tone.stop(now + ms / 1000 + 0.02);
}

/** A second passing. The last few are higher and louder — the same second,
 *  said more insistently. */
export const tick = (urgent = false) =>
	urgent ? blip(1180, 70, 0.09, 'triangle') : blip(760, 45, 0.045, 'triangle');

export const right = () => {
	blip(660, 90, 0.07);
	setTimeout(() => blip(990, 160, 0.07), 90);
};

export const wrong = () => blip(180, 260, 0.07, 'sawtooth');

/** The round is over. Three notes, so it is heard as an ending rather than as
 *  another answer. */
export const over = () => {
	[523, 659, 784].forEach((hz, i) => setTimeout(() => blip(hz, 220, 0.07), i * 130));
};

/** Silence, for a house that does not want a ticking television. Kept by the
 *  screen; there is nothing to remember here. */
export function muted(off: boolean) {
	if (!audio) return;
	if (off) void audio.suspend();
	else void audio.resume();
}
