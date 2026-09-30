// Moving a remote around a web page.
//
// A browser given an arrow key moves focus by its own rules, which were written
// for a keyboard walking a document: it follows source order as much as
// geometry, it will not leave a scrolling container it thinks it is inside, and
// it cannot see that the row of posters below the header is where a person
// looking at a television means to go. On a ten-foot surface that reads as a
// remote that does nothing. So on that surface, and only there, the arrows are
// answered here: what is nearest in the direction asked for, measured on the
// screen the person is actually looking at.

import { surface } from '$lib/keep/surface.svelte';
import { DIRECTIONS, PRESS, typing, type Direction } from '$lib/tvui/keys';
import { nav } from '$lib/tvui/nav.svelte';
import { showing } from '$lib/tvui/reach';
import { hero } from '$lib/keep/hero.svelte';

// Anything the remote may land on. A negative tabindex means a thing is
// reachable by name and not in the walk — the film's position bar says so about
// itself, and so does the record's — and this list has to honour that, or the
// key beside such a thing can never be reached: left and right belong to a
// focused slider and there is no way off it.
const NOT_SKIPPED = ':not([tabindex="-1"])';
const FOCUSABLE = [
	`a[href]${NOT_SKIPPED}`,
	`button:not([disabled])${NOT_SKIPPED}`,
	`input:not([disabled])${NOT_SKIPPED}`,
	`select:not([disabled])${NOT_SKIPPED}`,
	'[tabindex]:not([tabindex="-1"])'
].join(', ');

/* A card the remote can land on. `.card` is the design system's word for a card
   of any kind, and a season is one too — a section that opens, and that focus
   slides off without a sound, leaving the arrows dead on a page full of things
   to press. */
const CARD = `main .card:is(${FOCUSABLE})`;

/** What the screen looked like when this press arrived.
 *
 *  Every move reads the box of every focusable there is — three hundred of them
 *  on a wall of records — and a held arrow now takes four steps for one press.
 *  Measuring it again between them is four forced layouts of the whole page for
 *  one press of one key, and focusing a card in between is what forces them:
 *  that is what made a held arrow stutter on a wall. Nothing MOVES between the
 *  steps of one press — the page is scrolled by an animation that runs after
 *  the key has been dealt with — so one measurement serves the whole press, and
 *  is thrown away the moment it is over. */
let measured: { all: HTMLElement[] | null; rows: Partial<Record<Zone, Row[]>> } | null = null;

function candidates(): HTMLElement[] {
	if (measured?.all) return measured.all;
	// Something standing over the screen holds the remote: while it is up the
	// arrows must not walk the shelf behind it, which is what a menu you cannot
	// move around in looks like from the sofa.
	//
	// The transport is the exception, and it has to be: it lies over every
	// screen including the ones that hold the remote, and the keys for the song
	// you are listening to cannot be the one thing you may not reach.
	// the INNERMOST, not the first the document happens to mention. They nest —
	// a menu opened from the transport stands inside the transport's own held
	// region — and taking the first meant the arrows walked the bar and the menu
	// as one row, which is the output menu being unreachable as a list.
	const all = document.querySelectorAll<HTMLElement>('[data-holds-remote]');
	const held = all.length ? all[all.length - 1] : null;
	const roots: ParentNode[] = held
		? [held, ...document.querySelectorAll<HTMLElement>('[data-stays]')]
		: [document];
	const found = new Set<HTMLElement>();
	for (const root of roots) {
		for (const el of root.querySelectorAll<HTMLElement>(FOCUSABLE)) found.add(el);
	}
	const list = Array.from(found).filter((el) => {
		const box = el.getBoundingClientRect();
		if (box.width <= 0 || box.height <= 0) return false;
		// a shelf behind a playing film is hidden, not absent: it keeps its box,
		// so every poster on it stayed a place the remote could be sent
		return el.checkVisibility
			? el.checkVisibility({ visibilityProperty: true, opacityProperty: true })
			: getComputedStyle(el).visibility !== 'hidden';
	});
	if (measured) measured.all = list;
	return list;
}


/** The side of the screen something is on. The rail and the content are two
 *  places, not one field of things to aim at: going down a shelf must not walk
 *  off the bottom of it into the navigation, the way it would if the only rule
 *  were which candidate happened to be nearest. Sides are changed by saying so,
 *  with left and right. */
type Zone = 'rail' | 'scrub' | 'content';

function zoneOf(el: Element | null): Zone {
	if (el?.closest('nav.rail')) return 'rail';
	// The ruler down the side of a wall of photographs is a column of its own,
	// the same way the sections are. Read as part of the content it is rows
	// with the photographs beside it: walking down a wall of pictures steps
	// sideways into a month, and the years cannot be walked at all.
	if (el?.closest('.scrub')) return 'scrub';
	return 'content';
}

/** And the same again for left and right, where the bar that lies across the
 *  bottom is a third place. It is walked end to end with left and right and
 *  left with up and down — without that, left off the first of its keys landed
 *  in the navigation, because the navigation is what happens to be over there.
 *  The way into the sections is the way it has always been: left off the
 *  left-hand edge of the shelf itself. */
function sideOf(el: Element | null): 'rail' | 'bar' | 'content' {
	if (el?.closest('nav.rail')) return 'rail';
	if (el?.closest('.bar')) return 'bar';
	return 'content';
}

/** The screen as rows.
 *
 *  Nearest-in-that-direction is how this began, and on a page that is a stack of
 *  rows — chips, faces, seasons, records four across — it wanders: down from a
 *  button lands on whichever thing happens to be a few pixels lower, up from the
 *  same place does not come back, and two presses in a row change nothing. Every
 *  ten-foot interface answers the arrows the same way instead, and so does this
 *  one now: up and down are rows, left and right are along a row. It is one rule
 *  for every screen, which is the only way a remote becomes something you stop
 *  thinking about.
 *
 *  The rows are read off the screen rather than declared in the markup: whatever
 *  stands on the same line is a row, however it was built. */
type Row = { middle: number; items: HTMLElement[] };

function rowsIn(zone: Zone): Row[] {
	const had = measured?.rows[zone];
	if (had) return had;
	const placed = candidates()
		.filter((el) => zoneOf(el) === zone && sideOf(el) !== 'bar')
		.map((el) => ({ el, box: el.getBoundingClientRect() }))
		.sort((a, b) => a.box.top + a.box.height / 2 - (b.box.top + b.box.height / 2));

	const lines: { middle: number; items: { el: HTMLElement; left: number }[] }[] = [];
	for (const { el, box } of placed) {
		const middle = box.top + box.height / 2;
		const row = lines[lines.length - 1];
		// on the same line as the row being built, or the start of the next one.
		// Measured against the shorter of the two, so a poster does not swallow
		// the column of small things standing beside it
		const near = row && Math.abs(middle - row.middle) < Math.max(12, box.height * 0.6);
		if (near) row.items.push({ el, left: box.left });
		else lines.push({ middle, items: [{ el, left: box.left }] });
	}
	// along the line by the boxes already read: asking each of them again inside
	// a comparator is a measurement per comparison, of a page nothing has moved
	const rows = lines.map((line) => ({
		middle: line.middle,
		items: line.items.sort((a, b) => a.left - b.left).map((one) => one.el)
	}));
	if (measured) measured.rows[zone] = rows;
	return rows;
}

/** Which row something is in, and where along it. */
function place(rows: Row[], el: HTMLElement): { row: number; at: number } | null {
	for (let r = 0; r < rows.length; r++) {
		const at = rows[r].items.indexOf(el);
		if (at >= 0) return { row: r, at };
	}
	return null;
}

/** Coming into a row from above or below: the one thing chosen in it, when it
 *  has exactly one — entering a row of seasons on season one would show season
 *  one — and otherwise the thing standing in the same column, which is the one
 *  the eye is already on. */
function under(row: Row, from: DOMRect): HTMLElement {
	const chosen = row.items.filter((el) => el.classList.contains('on'));
	if (chosen.length === 1) return chosen[0];
	const middle = from.left + from.width / 2;
	let best = row.items[0];
	let bestScore = Infinity;
	for (const el of row.items) {
		const box = el.getBoundingClientRect();
		// standing in front of it counts as straight ahead, whatever the centres say
		const score =
			box.right > from.left && box.left < from.right
				? 0
				: Math.abs(box.left + box.width / 2 - middle);
		if (score < bestScore) {
			bestScore = score;
			best = el;
		}
	}
	return best;
}

/** The keys along the bottom, walked end to end. */
function barKeys(): HTMLElement[] {
	return candidates()
		.filter((el) => sideOf(el) === 'bar')
		.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
}

/** Where the remote was before it went down to the bar, so that coming back up
 *  is coming back rather than starting again. */
let leftBehind: HTMLElement | null = null;

/** Two presses further apart than this are two presses, not a hold. A remote
 *  repeats about every 100ms; a person pressing quickly on purpose lands inside
 *  this too, and that is the same intention said faster. */
const HELD_GAP = 260;

/** How far one press of a held arrow goes. It stays at one for the first few so
 *  that a glance down a shelf is exact, and opens up after that. */
function strides(run: number): number {
	if (run < 5) return 1;
	if (run < 11) return 2;
	return 4;
}

const KEYS = DIRECTIONS;

/** Leaving the content leftwards lands on the section you are already in, not
 *  on whichever link happens to be nearest the poster you were on — a sidebar
 *  is a list of places, and the place you are in is where the remote should
 *  arrive. */
function intoRail(): HTMLElement | null {
	const rail = document.querySelector('nav.rail');
	if (!rail) return null;
	return (
		rail.querySelector<HTMLElement>('a.here') ??
		rail.querySelector<HTMLElement>('a[href]:not(.who)')
	);
}

/** The page follows the remote instead of chasing it.
 *
 *  `scrollIntoView` cannot do this. A held arrow fires around thirty times a
 *  second and every smooth scroll started for one of them cancels the one
 *  before, so nothing ever finishes: measured against this page's own
 *  stylesheet, thirty presses walked the ring 2600 pixels down the shelf while
 *  the page travelled 240, and the rest of it arrived in a single jump the
 *  moment the key came up. Asking for the instant one instead does not help,
 *  because `behavior: 'auto'` means "whatever the stylesheet says" and the
 *  ten-foot stylesheet says smooth — the two branches were one branch.
 *
 *  So the scrolling is done here, as one animation that is never restarted. A
 *  press moves where the page is heading; the animation is already running and
 *  simply heads somewhere else. The page is the only thing on this surface that
 *  scrolls, so there is one of these and it belongs to the document. */
let following = 0;

/** Whatever actually scrolls around the target: the page on an ordinary screen,
 *  and the screen itself when something is standing over the page. A ring that
 *  walks into a box the page cannot scroll is a ring that leaves the screen. */
function scroller(el: HTMLElement): Element | null {
	let at: HTMLElement | null = el.parentElement;
	while (at) {
		const how = getComputedStyle(at).overflowY;
		if ((how === 'auto' || how === 'scroll') && at.scrollHeight > at.clientHeight + 1) return at;
		at = at.parentElement;
	}
	return document.scrollingElement;
}

function follow(target: HTMLElement) {
	const page = scroller(target);
	if (!page) return;
	// where the panel that keeps the top of the screen ends, and where the
	// bottom edge of a television begins
	const room = getComputedStyle(document.documentElement);
	const above = parseFloat(room.scrollPaddingTop) || 0;
	const below = parseFloat(room.scrollPaddingBottom) || 0;

	// a row is followed from its title down, so the title is never the part
	// left under the panel
	const whole = target.closest<HTMLElement>('[data-follow]');
	const step = () => {
		const card = target.getBoundingClientRect();
		const top = whole ? Math.min(card.top, whole.getBoundingClientRect().top) : card.top;
		const box = { top, bottom: card.bottom, height: card.bottom - top };
		// What is taller than the room left for it can never satisfy both edges,
		// and asking it to makes the shelf tremble: a card 270 tall in a band of
		// 244 is above the line and below it at once, so the correction changes
		// sign every frame and the page shakes until the remote moves.
		// Room is 540 css pixels on a television and the panel reserves 248 of
		// them, so this is the ordinary case there rather than a corner of one.
		// When it cannot fit, the top is the edge that matters.
		const seen = page === document.scrollingElement
			? { top: above, bottom: window.innerHeight - below }
			: (() => {
					const box = (page as HTMLElement).getBoundingClientRect();
					const own = getComputedStyle(page);
					return {
						top: box.top + (parseFloat(own.scrollPaddingTop) || 0),
						bottom: box.bottom - (parseFloat(own.scrollPaddingBottom) || 0)
					};
				})();
		const room = seen.bottom - seen.top;
		const fits = box.height <= room;
		const short = !fits
			? // Taller than the room left for it: both edges can never be inside
				// at once, so it is put at the top and left there. Asking for both
				// is what made the shelf tremble — the correction changed sign
				// every frame — and refusing the bottom edge without giving it the
				// top instead is what then pinned the shelf to its first row,
				// because a card below the fold was never above the line either.
				box.top - seen.top
			: box.top < seen.top
				? box.top - seen.top
				: box.bottom > seen.bottom
					? box.bottom - seen.bottom
					: 0;
		if (Math.abs(short) < 1) {
			following = 0;
			return;
		}
		// A quarter of what is left, each frame: it closes in about five of them,
		// which is soon enough that the ring never leaves the screen and gradual
		// enough to read as the page moving rather than cutting. The last few
		// pixels are taken whole so the end does not crawl.
		const by = Math.abs(short) < 6 ? short : short * 0.25;
		const was = page.scrollTop;
		page.scrollTo({ top: was + by, behavior: 'instant' });
		// Asked for and refused: the page is already at its end, or what has the
		// remote does not move with it — the rail is fixed to the side and sits
		// above the panel's line for as long as it holds focus. Either way there
		// is nothing further to do, and going round again is sixty frames a
		// second spent scrolling a page that cannot scroll.
		if (page.scrollTop === was) {
			following = 0;
			return;
		}
		following = requestAnimationFrame(step);
	};
	cancelAnimationFrame(following);
	following = requestAnimationFrame(step);
}

/** A row that is walked sideways — the billing, the facts about a copy — holds
 *  more than the screen shows, and the remote reaches the rest of it by moving
 *  along. The page scrolls itself for up and down; this is the same courtesy in
 *  the other direction, done to the row rather than to the page. */
function slide(target: HTMLElement) {
	let row: HTMLElement | null = target.parentElement;
	while (row && row.scrollWidth <= row.clientWidth + 1) row = row.parentElement;
	if (!row) return;
	const seen = row.getBoundingClientRect();
	const box = target.getBoundingClientRect();
	const air = 12;
	if (box.right > seen.right) row.scrollLeft += box.right - seen.right + air;
	else if (box.left < seen.left) row.scrollLeft -= seen.left - box.left + air;
}

function move(direction: Direction): boolean {
	const active = document.activeElement as HTMLElement | null;
	// Nothing holds the remote — a screen was just closed and took the focus
	// with it. Measured from a corner of nothing, every arrow lands wherever the
	// corner happens to point, which is how the first press after closing a
	// record went to the sections. The press puts the remote back on the page
	// instead, and the next one moves it.
	if (!active || active === document.body) {
		const back =
			showing(CARD) ??
			showing(`main :is(${FOCUSABLE}):not([data-aside], [data-aside] *)`) ??
			barKeys()[0];
		if (!back) return false;
		back.focus({ preventScroll: true });
		follow(back);
		return true;
	}
	// Something opened over the screen and the remote is still on what it
	// covered — the words to a song opened from the bar, and every arrow then
	// walked a list nobody can see. The press goes in.
	const reachable = candidates();
	if (!reachable.includes(active)) {
		const into = reachable[0];
		if (!into) return false;
		into.focus({ preventScroll: true });
		follow(into);
		return true;
	}

	const from = active.getBoundingClientRect();
	const side = sideOf(active);

	// The bar is a row of its own along the bottom: left and right walk it, up
	// gives the remote back to whatever was holding it, and there is nothing
	// under it.
	if (side === 'bar') {
		const keys = barKeys();
		const at = keys.indexOf(active);
		if (direction === 'left' || direction === 'right') {
			const next = keys[at + (direction === 'right' ? 1 : -1)];
			if (!next) return false;
			next.focus({ preventScroll: true });
			return true;
		}
		if (direction === 'up') {
			// where the remote came down from, if it is still there; otherwise the
			// last row of whatever is on the screen — which on a record is its
			// songs and never a poster on the shelf standing behind it
			const rows = rowsIn('content');
			const last = rows[rows.length - 1];
			const back =
				(leftBehind?.isConnected && candidates().includes(leftBehind) ? leftBehind : null) ??
				(last ? under(last, from) : null);
			if (!back) return false;
			back.focus({ preventScroll: true });
			follow(back);
			return true;
		}
		return false;
	}

	// Right off the sections is into what they hold — the first film, the first
	// record — and not into the questions above the shelf. Those are what
	// pressing the section is for. Said outright rather than left to geometry,
	// which measures the head of the shelf as nearer than its first poster.
	if (direction === 'right' && side === 'rail') {
		// The shelf on the screen is not the section the remote is standing on:
		// into what THIS section holds means making it the page first.
		const link = active.closest<HTMLAnchorElement>('a[href]');
		if (link && new URL(link.href).pathname !== nav.section) {
			link.click();
			return true;
		}
		// A wall of photographs keeps its ruler between the sections and the
		// pictures, and that is what right opens onto: the years stand nearer than
		// anything on the wall, and a year is a shorter way into forty thousand
		// photographs than the first of them. The wall is one press further right,
		// which is where it was anyway.
		if (rulerSide() === 'left') {
			const ruler = document.querySelector('.scrub');
			const year =
				ruler?.querySelector<HTMLElement>('.year.here') ??
				ruler?.querySelector<HTMLElement>('.year');
			if (year) {
				year.focus({ preventScroll: true });
				follow(year);
				return true;
			}
		}
		// a poster if the screen has posters, and otherwise whatever it does have:
		// a page about one film has none, and right off the sections there was
		// nowhere to go at all
		const first =
			showing(CARD) ?? showing(`main :is(${FOCUSABLE}):not([data-aside], [data-aside] *)`);
		if (first) {
			first.focus({ preventScroll: true });
			follow(first);
			return true;
		}
	}

	const zone = zoneOf(active);
	const rows = rowsIn(zone);
	const here = place(rows, active);
	if (!here) return false;

	let target: HTMLElement | null = null;
	if (direction === 'left' || direction === 'right') {
		target = rows[here.row].items[here.at + (direction === 'right' ? 1 : -1)] ?? null;
		// Off the left-hand edge, which means two different things at the two
		// levels. On the menu screen it is
		// the sections, landing on the one you are in rather than on whichever
		// link sits at that height. On a page that has taken the screen there is
		// no menu to reach, so it is the header — where the way back is the first
		// control, because a way out you reach only by remembering a key is a way
		// out people do not find.
		// Between a wall of photographs and its ruler: out of the ruler towards
		// the pictures is onto the pictures it measures, and towards the ruler is
		// into it. Which way that is gets read off the screen — a desk keeps the
		// ruler by the scrollbar, a television before the grid.
		const ruler = zone === 'rail' ? null : rulerSide();
		if (!target && ruler) {
			// Out of the ruler towards the pictures: the wall goes where the ruler
			// left it and what is on the screen is read when it gets there. Choosing
			// by geometry first takes a photograph from the view the ruler is about
			// to replace, and following it then drags the wall back to it.
			if (zone === 'scrub' && direction !== ruler) {
				active.blur();
				intoWall();
				return true;
			}
			if (zone === 'content' && direction === ruler) target = beside('scrub', from);
		}
		if (!target && direction === 'left') {
			if (confined()) target = intoHeader();
			else if (zone !== 'rail') target = intoRail();
		}
	} else {
		const row = rows[here.row + (direction === 'down' ? 1 : -1)];
		if (row) target = under(row, from);
		// Down off the last row is the bar, if something is playing: the one place
		// left to go, and the way back up is where you were.
		else if (direction === 'down') {
			const key = barKeys()[0];
			if (key) {
				leftBehind = active;
				key.focus({ preventScroll: true });
				return true;
			}
		}
		// Up from the top of the shelf is the shelf's own head: how much is on it
		// and where else to look. It is drawn in the panel, and the panel is
		// describing whatever poster the remote is on — so the description is
		// dropped first and the head is what is there a moment later.
		else if (direction === 'up' && zone === 'content' && toHead(active)) return true;
		// Up off the top of a column is whatever stands above the column, which
		// is the page's own head and belongs to the content beside it.
		else if (direction === 'up' && zone === 'scrub') target = above(from);
	}
	if (!target) return false;
	target.focus({ preventScroll: true });
	slide(target);
	follow(target);
	return true;
}

/** Hand the ring to the wall a ruler has just jumped to.
 *
 *  The jump is a smooth scroll, so what is under the ring a frame later is still
 *  whatever was there before it started moving. This waits for the page to come
 *  to rest and then takes the first picture actually on the screen — not the
 *  first in the document, which after a jump to 2013 is a photograph from this
 *  year, off the top of a screen showing something else entirely. */
function intoWall() {
	const ruler = document.querySelector('.scrub');
	const wall = ruler?.parentElement?.querySelector<HTMLElement>(':scope > :not(.scrub)');
	if (!wall) return;
	// The wall's own top, not the window's scroll: a ten-foot page is fixed and
	// scrolls a box inside itself, so the window never moves and every jump
	// looked to this as if it had already arrived.
	let last = Number.NaN;
	let waited = 0;
	const timer = setInterval(() => {
		waited += 1;
		const at = Math.round(wall.getBoundingClientRect().top);
		if (at !== last && waited < 45) {
			last = at;
			return;
		}
		clearInterval(timer);
		const page = scroller(wall);
		const seen =
			!page || page === document.scrollingElement
				? { top: 0, bottom: window.innerHeight }
				: (page as HTMLElement).getBoundingClientRect();
		const first = candidates().find((el) => {
			if (!el.matches('.cell')) return false;
			const box = el.getBoundingClientRect();
			return box.top >= seen.top && box.bottom <= seen.bottom;
		});
		first?.focus({ preventScroll: true });
	}, 40);
}

/** Crossing from one column into the one beside it: the one thing chosen in
 *  it, when it has exactly one — the season whose episodes are beside it — and
 *  otherwise the row of that zone nearest this height, and the thing on it
 *  nearest this edge. */
function beside(zone: Zone, from: DOMRect): HTMLElement | null {
	const rows = rowsIn(zone);
	if (!rows.length) return null;
	const chosen = rows.flatMap((row) => row.items).filter((el) => el.classList.contains('on'));
	if (chosen.length === 1) return chosen[0];
	const middle = from.top + from.height / 2;
	let best = rows[0];
	for (const row of rows) {
		if (Math.abs(row.middle - middle) < Math.abs(best.middle - middle)) best = row;
	}
	return under(best, from);
}

/** The content row nearest over this, and the thing on it nearest this edge. */
function above(from: DOMRect): HTMLElement | null {
	const over = rowsIn('content').filter((row) => row.middle < from.top);
	return over.length ? under(over[over.length - 1], from) : null;
}

/** Which side of its wall the ruler stands on, or nothing when there is none. */
function rulerSide(): 'left' | 'right' | null {
	const ruler = document.querySelector('.scrub');
	const wall = ruler?.parentElement?.querySelector(':scope > :not(.scrub)');
	if (!ruler || !wall) return null;
	return ruler.getBoundingClientRect().left < wall.getBoundingClientRect().left ? 'left' : 'right';
}

/** Something is standing over the screen and holding the remote — a record, the
 *  words to a song, a list of languages. The sections are not reachable from
 *  inside one: the way out is back, not left. */
/** The way out of a page that has taken the screen: the first control of its
 *  header, which is the way back. Asked only from inside such a page, so it
 *  looks inside the held region and nowhere else — the frame's own header
 *  belongs to the screen underneath. */
function intoHeader(): HTMLElement | null {
	const all = document.querySelectorAll<HTMLElement>('[data-holds-remote]');
	const held = all.length ? all[all.length - 1] : null;
	if (!held) return null;
	return held.querySelector<HTMLElement>(FOCUSABLE);
}

function confined(): boolean {
	return Boolean(document.querySelector('[data-holds-remote]'));
}

function toHead(from: HTMLElement): boolean {
	// `.hero` and `.said` stopped existing when the head became the shared
	// PageHead, whose wrapper is `.head`. Nothing errored: a selector that
	// matches nothing simply returns early, so going up into the head quietly
	// did nothing at all on every screen, and pressing a section handed the
	// remote to the document body.
	// A head with nothing in it to press — a person's portrait and their story —
	// is still what is up there, and the top of the page is where it is read.
	const page = scroller(from);
	const top = () => page?.scrollTo({ top: 0, behavior: 'instant' });
	if (!document.querySelector('.head')) {
		if (!page || page.scrollTop <= 0) return false;
		top();
		return true;
	}
	hero.forget();
	queueMicrotask(() => {
		const first = document.querySelector<HTMLElement>('.head .ways button');
		first?.focus({ preventScroll: true });
		top();
	});
	return true;
}

/** Put the remote on the first thing inside something that just appeared. A
 *  panel that opens with nothing focused is a panel where pressing OK does
 *  nothing, which reads as a play button that does not work. */
export function focusFirst(selector: string) {
	showing(selector)?.focus({ preventScroll: true });
}

/** The same, for something that is not drawn yet.
 *
 *  Asking once is right where the thing is already on the screen — a row of
 *  ways, a list of orders. It is wrong where the thing arrives from the
 *  library: an artist's records are fetched after the screen about them is
 *  built, so the one ask found nothing, the remote was left on the document and
 *  no arrow moved. Tries at once, then keeps trying for three seconds, and
 *  stands down the moment anything else holds the remote. */
export function focusWaiting(selector: string): () => void {
	let attempts = 0;
	let timer: ReturnType<typeof setInterval>;
	const tick = () => {
		attempts += 1;
		const active = document.activeElement as HTMLElement | null;
		if (active && active !== document.body) return clearInterval(timer);
		// same rule as the lander below: the next tick is what confirms it stuck
		showing(selector)?.focus({ preventScroll: true });
		if (attempts > 20) clearInterval(timer);
	};
	timer = setInterval(tick, 150);
	tick();
	return () => clearInterval(timer);
}

/** The first thing a person looking at a television means to be on: the content,
 *  not the account button the document happens to reach first.
 *
 *  Kept trying for a few seconds rather than done once: the rows arrive from the
 *  library after the frame does, and a single attempt fires at a page that has
 *  no posters in it yet and quietly does nothing. */
export function focusContent(): () => void {
	let attempts = 0;
	const timer = setInterval(() => {
		attempts += 1;
		const active = document.activeElement as HTMLElement | null;
		// Anything already holding the remote wins, including a panel that opened
		// while this was still waiting for posters — carrying on would take focus
		// off the play button a moment after it landed there, which is a play
		// button that works only when the page was quick.
		if (active && active !== document.body) {
			clearInterval(timer);
			return;
		}
		// A poster first. Then anything else the page offers, because a page of
		// settings has no posters and leaving the remote on the document there is
		// a page whose arrows do nothing — but not the way out to another
		// application, which is somewhere to go and not what the page is about.
		// That one is taken only when nothing else ever turns up.
		const card =
			showing(CARD) ??
			(attempts > 3
				? showing(`main :is(${FOCUSABLE}):not([data-aside], [data-aside] *)`)
				: null) ??
			(attempts >= 20 ? showing(`main :is(${FOCUSABLE})`) : null);
		// Landing is not the same as having landed. A wall of photographs is still
		// being built at this point: the tile the ring is handed to is replaced a
		// moment later, focus falls back to the document, and nobody was left
		// watching — "I picked her and the remote stopped working". So this does
		// not stop on success. The next tick sees the ring held and stops there,
		// or it lands again.
		if (card) {
			// whatever the head was saying was about a tile that may no longer be
			// here — a shelf replaced while its answer was being fetched
			hero.forget();
			hero.hush();
			card.focus({ preventScroll: true });
		}
		if (attempts > 20) {
			clearInterval(timer);
		}
	}, 150);
	return () => clearInterval(timer);
}

export function arrows() {
	let held = false;
	// how many presses of the same arrow have arrived without a pause, and when
	// the last one was. A remote held down repeats, and not every repeat says so
	// — `event.repeat` is false on the boxes in this house — so the gap between
	// presses is what tells a hold from a press.
	let run = 0;
	let ranWay: Direction | null = null;
	let ranAt = 0;

	function onkeyup(event: KeyboardEvent) {
		if (PRESS.has(event.key)) held = false;
	}

	// A press that opens another app lifts the key over there.
	function onleave() {
		held = false;
	}

	function onkeydown(event: KeyboardEvent) {
		if (!surface.isTv || event.defaultPrevented) return;
		const active = document.activeElement as HTMLElement | null;

		// OK, answered here rather than by each screen catching Enter for itself.
		// The rule is one a screen can be held to: if the remote can land on it,
		// it is a button or a link, and OK presses it. Anything that wants the
		// key for something else says so with data-ok and gets it untouched.
		if (PRESS.has(event.key)) {
			if (typing(active) || !active || active.dataset.ok !== undefined) return;
			if (active.tagName === 'BUTTON' || active.tagName === 'A') {
				// The remote repeats OK while it is held, and not every repeat says
				// so; one hold is one press until the key comes up.
				if (held) {
					event.preventDefault();
					return;
				}
				held = true;
				const ruler = active.closest('.scrub') && active.dataset.stay === undefined;
				active.click();
				event.preventDefault();
				// A ruler is a way INTO what it measures: pressing a month is asking
				// to look at that month, not to stand on its label. The wall jumps
				// and the ring goes with it, once the jump has arrived — the surface
				// scrolls smoothly, so what is under the ring a frame later is still
				// wherever it was before. A mark whose press opens more of the ruler
				// says data-stay, because handing the ring to the wall would leave
				// what it just opened behind.
				if (ruler) intoWall();
			}
			return;
		}

		const direction = KEYS[event.key];
		if (!direction) return;
		hero.wake();
		// a text field owns its own arrows — moving the caret is not moving focus
		if (typing(active)) return;
		// An arrow held down goes faster. A wall of two hundred records is four
		// rows a screen, too long to cross one row at a time. Only the LENGTH of
		// the press changes the step: one press is always one thing, so nothing
		// moves under somebody who is aiming.
		//
		// The shelf only. The sections are a dozen names and a ruler is already
		// the quick way across what it measures — a year skipped there is the
		// year somebody was going to, and it is the third press of the same key
		// that skips it.
		const now = performance.now();
		run = direction === ranWay && now - ranAt < HELD_GAP ? run + 1 : 0;
		ranWay = direction;
		ranAt = now;
		const far = zoneOf(active) === 'content' ? strides(run) : 1;
		measured = { all: null, rows: {} };
		for (let step = 0; step < far; step++) {
			if (!move(direction)) break;
		}
		measured = null;
		// The arrows belong to the surface, whether or not there was anywhere to
		// go. Left to the browser, a press with nothing in that direction slides
		// the page while the ring stays where it was — which from a sofa is a
		// screen that moved on its own.
		event.preventDefault();
	}

	// Where the ring is, noted wherever it goes and whoever sent it there. A
	// component that moves focus itself is recorded exactly like a person
	// pressing an arrow, because from the sofa those are the same event.
	function onfocusin(event: FocusEvent) {
		nav.remember(event.target as Element | null);
	}

	window.addEventListener('keydown', onkeydown);
	window.addEventListener('keyup', onkeyup);
	window.addEventListener('blur', onleave);
	document.addEventListener('visibilitychange', onleave);
	window.addEventListener('focusin', onfocusin);
	return () => {
		window.removeEventListener('keydown', onkeydown);
		window.removeEventListener('keyup', onkeyup);
		window.removeEventListener('blur', onleave);
		document.removeEventListener('visibilitychange', onleave);
		window.removeEventListener('focusin', onfocusin);
	};
}
