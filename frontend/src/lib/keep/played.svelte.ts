/** Whether a round is being played.
 *
 * The section around the game — its title, its counts, its row of ways — is
 * how somebody arrives at it and has nothing to do with a question being
 * asked. On a phone that chrome was the top third of the screen while a clock
 * was running, so the picture the whole question is about had what was left.
 *
 * A flag rather than a prop because the section draws its own head above a
 * child that knows nothing about it, and nothing is written into it from a
 * derivation the section itself feeds. */
class Played {
	playing = $state(false);
}

export const played = new Played();
