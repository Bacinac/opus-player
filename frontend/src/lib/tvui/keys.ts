/* What a remote's keys mean, in one place.
 *
 * They were scattered: the four arrows here, OK nowhere at all, and three
 * screens each catching Enter on their own in a capture-phase listener so that
 * whatever the surface might have done never got the chance. A key that means
 * one thing on one screen and another on the next is a remote nobody can learn.
 */

export type Direction = 'up' | 'down' | 'left' | 'right';

export const DIRECTIONS: Record<string, Direction> = {
	ArrowUp: 'up',
	ArrowDown: 'down',
	ArrowLeft: 'left',
	ArrowRight: 'right'
};

/** Every key an Android TV remote sends for the centre button. A D-pad centre
 *  arrives as Enter, a keyboard's numeric enter as NumpadEnter, and a browser
 *  treats Space as a press only on some elements — so all three are said here
 *  rather than discovered one screen at a time. */
export const PRESS = new Set(['Enter', 'NumpadEnter', ' ', 'Spacebar']);

/** How far one skip moves what is playing, in seconds: an arrow over a film and
 *  the remote's own fast-forward and rewind keys are the same step. */
export const SKIP_S = 10;

/** Where a key must be left alone: a text field owns its own arrows, because
 *  moving the caret is not moving focus. */
export function typing(el: Element | null): boolean {
	return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement;
}
