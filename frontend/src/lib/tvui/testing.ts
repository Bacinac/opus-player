/* A screen for the ten-foot tests: markup whose boxes are stated rather than
 * laid out. The test DOM has no layout engine, so every box would be empty and
 * every element invisible; `data-box="left top width height"` says where each
 * thing stands on a 960x540 television instead. */

function box(el: Element): DOMRect {
	const [left, top, width, height] = ((el as HTMLElement).dataset?.box ?? '0 0 0 0')
		.split(' ')
		.map(Number);
	return {
		x: left,
		y: top,
		left,
		top,
		width,
		height,
		right: left + width,
		bottom: top + height,
		toJSON: () => ({})
	} as DOMRect;
}

let installed = false;

export function draw(html: string) {
	if (!installed) {
		installed = true;
		Element.prototype.getBoundingClientRect = function (this: Element) {
			return box(this);
		};
		Element.prototype.getClientRects = function (this: Element) {
			const one = box(this);
			return (one.width && one.height ? [one] : []) as unknown as DOMRectList;
		};
		HTMLElement.prototype.checkVisibility = () => true;
		Element.prototype.scrollIntoView = () => {};
		window.requestAnimationFrame = () => 0;
	}
	document.body.innerHTML = html;
	(document.activeElement as HTMLElement | null)?.blur();
}

export const at = (selector: string) => document.querySelector<HTMLElement>(selector)!;

export const focused = () => document.activeElement as HTMLElement | null;
