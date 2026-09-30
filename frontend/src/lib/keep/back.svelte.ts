// What back means, in one place.
//
// Back on a remote is not the browser's history. It takes away the topmost
// thing standing over what you were looking at — a panel, a list of letters, a
// film — and only when nothing is standing over anything does it mean leave.
// Every part that can be on top says so here rather than each of them fighting
// over window.opusBack, which is what the wrapper asks.

/** Returns true when this step swallowed the press. */
export type Step = () => boolean;

/** Whether this step would swallow a press RIGHT NOW.
 *
 * Registering is not holding: the home page keeps a step for closing the record
 * it has open, and keeps it whether or not one is open. Counting registrations
 * therefore said "there is a way back" on the first screen of the app, which is
 * the one place there is not. Asking `goBack()` cannot answer it either —
 * answering that question is doing it. So a step that wants to be SEEN says
 * for itself. */
type Holding = () => boolean;

const steps: Step[] = [];
const holds = new Map<Step, Holding>();

// Bumped whenever a rung comes or goes, so a derivation that ran before any of
// them existed is asked again once they do — the frame renders before the page
// it holds, so without this it reads an empty ladder, depends on nothing, and
// never runs again.
//
// Counted OUTSIDE the signal and only assigned into it. `n += 1` would READ n,
// and reading a state inside the effect that writes it is an effect that
// invalidates itself: the update loop that turned the whole app white.
let turns = 0;
let churn = $state(0);

export const ladder = {
	/** Whether anything would answer a press. Read inside a $derived: calling
	 *  each holder here is what makes that derivation depend on THEIR state,
	 *  which is the only dependency it needs — a rung appears or disappears
	 *  because something it watches changed, and that change is what re-runs
	 *  this. Nothing reactive is written when a rung registers: `onBack` is
	 *  called from inside an effect, and a write there feeding a derivation the
	 *  frame reads is an update loop, which is a blank screen. */
	holding(): boolean {
		void churn;
		for (const step of steps) {
			const held = holds.get(step);
			if (held && held()) return true;
		}
		return false;
	}
};

/** Register while mounted. The most recently registered is asked first, which
 *  is what "topmost" means when things open over one another. */
export function onBack(step: Step, holding?: Holding): () => void {
	steps.unshift(step);
	if (holding) holds.set(step, holding);
	churn = ++turns;
	return () => {
		const at = steps.indexOf(step);
		if (at >= 0) steps.splice(at, 1);
		holds.delete(step);
		churn = ++turns;
	};
}

export function goBack(): boolean {
	for (const step of [...steps]) {
		if (step()) return true;
	}
	return false;
}
