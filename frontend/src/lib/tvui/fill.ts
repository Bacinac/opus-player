import type { Action } from 'svelte/action';

/**
 * Gives a box the height left to it under whatever stands above it, so the box
 * scrolls inside itself. A television's stage does not scroll the page: a list
 * taller than the screen would take the remote out of sight.
 */
export const fill: Action<HTMLElement> = (box) => {
	// down to where the box it lies in stops showing things, which is the
	// screen's edge on a page and the stage's padding over a transport bar
	const measure = () => {
		// The root is the window, whatever it computes: overflow-x hidden on it
		// turns its overflow-y into auto, and its box ends where the document
		// does — a few lines down on a page whose contents are all fixed.
		let holder = box.parentElement;
		while (
			holder &&
			holder !== document.documentElement &&
			!/auto|scroll/.test(getComputedStyle(holder).overflowY)
		)
			holder = holder.parentElement;
		if (holder === document.documentElement) holder = null;
		const bottom = holder
			? holder.getBoundingClientRect().bottom - parseFloat(getComputedStyle(holder).paddingBottom)
			: window.innerHeight -
				(parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--tv-bar-h')) || 0);
		box.style.height = `${Math.max(160, bottom - box.getBoundingClientRect().top - 16)}px`;
	};
	measure();
	// A head that settles after the box has mounted — its picture arrives, its
	// facts load — moves the box without resizing anything the box is inside,
	// so what stands above it is watched as well.
	const watch = new ResizeObserver(measure);
	watch.observe(document.body);
	for (let at: Element | null = box; at && at !== document.body; at = at.parentElement) {
		for (let above = at.previousElementSibling; above; above = above.previousElementSibling)
			watch.observe(above);
	}
	return {
		destroy() {
			watch.disconnect();
			box.style.height = '';
		}
	};
};
