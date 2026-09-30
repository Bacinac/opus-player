/** The edge of a row that is walked sideways.
 *
 * `slide()` already carries the ring past the edge of a row that holds more
 * than the screen shows — the billing, the facts about a copy. Nothing said
 * there WAS more: the last face stood flush against the edge and read as the
 * end of the cast. This fades the side that has more, and leaves a row that
 * fits alone.
 */
export function sideways(row: HTMLElement) {
	const tell = () => {
		const before = row.scrollLeft > 1;
		const after = row.scrollLeft + row.clientWidth < row.scrollWidth - 1;
		const side = before && after ? 'both' : before ? 'before' : after ? 'after' : '';
		if (side) row.dataset.more = side;
		else delete row.dataset.more;
	};

	tell();
	row.addEventListener('scroll', tell, { passive: true });
	// a face that arrives is a row that grew, and pictures arrive after the row
	// has already been measured. Capture, because load does not bubble.
	row.addEventListener('load', tell, true);
	const watch = new ResizeObserver(tell);
	watch.observe(row);

	return {
		destroy() {
			row.removeEventListener('scroll', tell);
			row.removeEventListener('load', tell, true);
			watch.disconnect();
		}
	};
}
