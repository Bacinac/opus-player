/** The first thing matching that can actually take the ring.
 *
 * `querySelector` answers with the first match in the document, and a page
 * carries things that match every focus selector and cannot be focused at all:
 * the hidden file input the frame keeps for handing over photographs is the
 * first `input` on every page in this application. Focusing something with no
 * box does nothing, and does it silently — so a lander that treats the call as
 * success leaves the remote on the document with every arrow dead, which is
 * what "I picked her and the remote stopped working" was.
 *
 * `offsetParent` alone is not the question: it is null for anything positioned
 * fixed, which the bar along the bottom is.
 */
export function showing(selector: string, root: ParentNode = document): HTMLElement | null {
	for (const el of root.querySelectorAll<HTMLElement>(selector)) {
		if (el.matches(':disabled')) continue;
		if (el.offsetParent || el.getClientRects().length) return el;
	}
	return null;
}
