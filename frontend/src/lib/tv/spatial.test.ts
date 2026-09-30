// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { at, draw, focused } from '$lib/tvui/testing';

const tv = vi.hoisted(() => ({
	surface: { isTv: true },
	page: { url: new URL('http://tv.test/music') }
}));
vi.mock('$app/state', () => ({ page: tv.page }));
vi.mock('$lib/keep/surface.svelte', () => ({ surface: tv.surface }));
vi.mock('$lib/keep/hero.svelte', () => ({ hero: { wake() {}, forget() {}, hush() {} } }));

import { arrows } from './spatial.svelte';

let clock = 0;
let stop: () => void;

beforeEach(() => {
	tv.surface.isTv = true;
	tv.page.url = new URL('http://tv.test/music');
	vi.spyOn(performance, 'now').mockImplementation(() => clock);
	stop = arrows();
});

afterEach(() => {
	stop();
	vi.restoreAllMocks();
});

/** One press, a second after the last one unless said otherwise: a pause long
 *  enough that it is never read as a key held down. */
function press(key: string, after = 1000): KeyboardEvent {
	clock += after;
	const event = new KeyboardEvent('keydown', { key, cancelable: true, bubbles: true });
	window.dispatchEvent(event);
	return event;
}

function lift(key: string) {
	window.dispatchEvent(new KeyboardEvent('keyup', { key }));
}

/** The menu down the side, two rows of three posters, and whatever else the
 *  screen is given inside its main part. The link for films stands level with
 *  the first row, nearer to it than the section the remote is in. */
function shelf(inside = '', after = '') {
	draw(`
		<nav class="rail">
			<a href="/films" id="films" data-box="40 100 120 30">Filmovi</a>
			<a href="/music" id="music" class="here" data-box="40 300 120 30">Glazba</a>
		</nav>
		<main>
			${inside}
			<a href="#" class="card" id="a1" data-box="200 100 100 150"></a>
			<a href="#" class="card" id="a2" data-box="320 100 100 150"></a>
			<a href="#" class="card" id="a3" data-box="440 100 100 150"></a>
			<a href="#" class="card" id="b1" data-box="200 280 100 150"></a>
			<a href="#" class="card" id="b2" data-box="320 280 100 150"></a>
			<a href="#" class="card" id="b3" data-box="440 280 100 150"></a>
		</main>
		${after}`);
}

const BAR = `
	<div class="bar" data-stays>
		<button id="prev" data-box="300 500 40 30"></button>
		<button id="play" data-box="350 500 40 30"></button>
	</div>`;

describe('up and down are rows', () => {
	test('down is the row below, in the same column, and up comes back', () => {
		shelf();
		at('#a2').focus();
		press('ArrowDown');
		expect(focused()?.id).toBe('b2');
		press('ArrowUp');
		expect(focused()?.id).toBe('a2');
	});

	test('a row with one thing chosen is entered on it', () => {
		shelf();
		at('#b3').classList.add('on');
		at('#a1').focus();
		press('ArrowDown');
		expect(focused()?.id).toBe('b3');
	});

	test('the arrows belong to the surface even where there is nowhere to go', () => {
		shelf();
		at('#a3').focus();
		const event = press('ArrowRight');
		expect(focused()?.id).toBe('a3');
		expect(event.defaultPrevented).toBe(true);
	});
});

describe('the sections', () => {
	test('left off the shelf is the section you are in, not the nearest link', () => {
		shelf();
		at('#a1').focus();
		press('ArrowLeft');
		expect(focused()?.id).toBe('music');
	});

	test('right off the section you are in is into its shelf', () => {
		shelf();
		at('#music').focus();
		press('ArrowRight');
		expect(focused()?.id).toBe('a1');
	});

	test('right off another section opens that section first', () => {
		shelf();
		const opened = vi.fn((event: Event) => event.preventDefault());
		at('#films').addEventListener('click', opened);
		at('#films').focus();
		press('ArrowRight');
		expect(opened).toHaveBeenCalledOnce();
		expect(focused()?.id).toBe('films');
	});
});

describe('the bar along the bottom', () => {
	test('down off the last row is the bar, walked sideways, and up is where you were', () => {
		shelf('', BAR);
		at('#b2').focus();
		press('ArrowDown');
		expect(focused()?.id).toBe('prev');
		press('ArrowRight');
		expect(focused()?.id).toBe('play');
		press('ArrowUp');
		expect(focused()?.id).toBe('b2');
	});
});

describe('something standing over the screen', () => {
	const OVER = `
		<section data-holds-remote>
			<button id="back" data-box="60 20 80 30"></button>
			<button id="x1" class="card" data-box="200 200 120 40"></button>
			<button id="x2" class="card" data-box="340 200 120 40"></button>
		</section>`;

	test('holds the remote: the shelf behind it cannot be reached', () => {
		shelf(OVER);
		at('#x2').focus();
		press('ArrowDown');
		expect(focused()?.id).toBe('x2');
		press('ArrowUp');
		expect(focused()?.id).toBe('back');
	});

	test('left off its edge is its own way back, not the sections', () => {
		shelf(OVER);
		at('#x1').focus();
		press('ArrowLeft');
		expect(focused()?.id).toBe('back');
	});

	test('a press on what it covered goes in', () => {
		shelf(OVER);
		at('#a1').focus();
		press('ArrowRight');
		expect(focused()?.id).toBe('back');
	});
});

describe('held', () => {
	const LONG = `<main>${Array.from(
		{ length: 20 },
		(_, i) => `<a href="#" class="card" id="c${i}" data-box="${200 + i * 110} 100 100 150"></a>`
	).join('')}</main>`;

	test('a held arrow opens up after five, and a press after a pause is one again', () => {
		draw(LONG);
		at('#c0').focus();
		for (let i = 0; i < 6; i++) press('ArrowRight', 100);
		// five single steps, then the sixth repeat takes two
		expect(focused()?.id).toBe('c7');
		press('ArrowRight');
		expect(focused()?.id).toBe('c8');
	});

	test('the sections are never skipped through', () => {
		draw(
			`<nav class="rail">${Array.from(
				{ length: 12 },
				(_, i) => `<a href="/s${i}" id="s${i}" data-box="40 ${40 * i} 120 30"></a>`
			).join('')}</nav><main></main>`
		);
		at('#s0').focus();
		for (let i = 0; i < 8; i++) press('ArrowDown', 100);
		expect(focused()?.id).toBe('s8');
	});
});

describe('where nothing holds the remote', () => {
	test('the first press puts it on the first poster rather than moving from a corner', () => {
		shelf('', BAR);
		press('ArrowDown');
		expect(focused()?.id).toBe('a1');
	});

	test('a text field keeps its own arrows', () => {
		shelf('<input id="q" data-box="200 20 300 40" />');
		at('#q').focus();
		const event = press('ArrowDown');
		expect(focused()?.id).toBe('q');
		expect(event.defaultPrevented).toBe(false);
	});

	test('off the television the arrows are the browser’s', () => {
		tv.surface.isTv = false;
		shelf();
		at('#a1').focus();
		const event = press('ArrowRight');
		expect(focused()?.id).toBe('a1');
		expect(event.defaultPrevented).toBe(false);
	});
});

describe('OK', () => {
	test('presses what the remote is on, once for as long as it is held', () => {
		draw(`<main><button id="go" data-box="200 100 100 40"></button></main>`);
		const pressed = vi.fn();
		at('#go').addEventListener('click', pressed);
		at('#go').focus();
		press('Enter');
		press('Enter', 100);
		expect(pressed).toHaveBeenCalledOnce();
		lift('Enter');
		press('Enter');
		expect(pressed).toHaveBeenCalledTimes(2);
	});

	test('is left alone where something asked for it', () => {
		draw(`<main><button id="go" data-ok data-box="200 100 100 40"></button></main>`);
		const pressed = vi.fn();
		at('#go').addEventListener('click', pressed);
		at('#go').focus();
		const event = press('Enter');
		expect(pressed).not.toHaveBeenCalled();
		expect(event.defaultPrevented).toBe(false);
	});
});
