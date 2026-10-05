export class Crossfade {
	private frame: number | null = null;
	private generation = 0;
	private decks: [HTMLAudioElement, HTMLAudioElement] | null = null;

	constructor(private changed: (active: boolean) => void) {}

	start(going: HTMLAudioElement, coming: HTMLAudioElement, src: string, seconds: number,
		play: (deck: HTMLAudioElement, valid: () => boolean) => void,
		valid: () => boolean, complete: () => void) {
		if (this.decks) return;
		const generation = ++this.generation;
		const current = () => generation === this.generation && valid();
		this.decks = [going, coming];
		this.changed(true);
		coming.src = src;
		coming.volume = 0;
		coming.currentTime = 0;
		play(coming, current);
		const began = performance.now();
		const step = () => {
			if (generation !== this.generation) return;
			if (!valid()) { this.cancel(); return; }
			const through = Math.min(1, (performance.now() - began) / (seconds * 1000));
			going.volume = 1 - through;
			coming.volume = through;
			if (through < 1) { this.frame = requestAnimationFrame(step); return; }
			this.frame = null;
			this.decks = null;
			++this.generation;
			going.pause();
			going.volume = 1;
			this.changed(false);
			complete();
		};
		this.frame = requestAnimationFrame(step);
	}

	cancel() {
		++this.generation;
		if (this.frame !== null) cancelAnimationFrame(this.frame);
		this.frame = null;
		for (const deck of this.decks ?? []) { deck.pause(); deck.volume = 1; }
		this.decks = null;
		this.changed(false);
	}
}
