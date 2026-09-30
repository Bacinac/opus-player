import type { Profile } from '$lib/keep/types';

/** Who is watching, as opposed to who signed in.
 *
 * The account came through the door and carries what somebody is allowed to do;
 * the profile is whose evening it is, and the two are not the same person even
 * when they are the same human. Kept here rather than in the frame because
 * leaving a profile is offered on the settings page, beside signing out, and a
 * page cannot reach a variable that lives in the layout above it.
 *
 * Letting go of one is not signing out: it asks "who is watching?" again and
 * costs nothing. Signing out ends the session and asks for a password. */
class Watching {
	profile = $state<Profile | null>(null);
	/** the name on the roster, where somebody came through the door as
	 *  themselves. Empty on a television, which is let in as a box and is
	 *  nobody, so what belongs to one person is not drawn there at all. */
	person = $state('');

	/** Put the question back. */
	again() {
		this.profile = null;
	}
}

export const watching = new Watching();
