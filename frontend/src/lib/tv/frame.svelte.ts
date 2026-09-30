// What the frame does only because it is on a television. Called once from the
// root layout while it initialises; everything here is an effect that stands
// down wherever the surface is not a television.

import { page } from '$app/state';
import { me } from '$lib/opus';
import { goBack } from '$lib/keep/back.svelte';
import { preview } from '$lib/keep/preview.svelte';
import { surface } from '$lib/keep/surface.svelte';
import { watching } from '$lib/keep/watching.svelte';
import { nav } from '$lib/tvui/nav.svelte';
import { playKey } from './playkey';
import { focusWaiting } from './spatial.svelte';

export function tvFrame() {
	// the document itself has to know, because what a television needs changed
	// about it — its scrollbar, how it scrolls — is not inside any component
	$effect(() => {
		document.documentElement.classList.toggle('tv', surface.isTv);
	});

	$effect(() => {
		if (!surface.isTv) return;
		window.addEventListener('keydown', playKey);
		return () => window.removeEventListener('keydown', playKey);
	});

	// The browser's own back is not asked: by the time it pops, the browser has
	// spent a real entry, so the address moves while the screen does not — back
	// on the records would leave the address saying home with the records still
	// on it, and the menu underlining a page nobody is on. One entry is kept in
	// hand and given back on every pop, and the ladder answers instead.
	$effect(() => {
		if (!surface.isTv) return;
		function onpop() {
			goBack();
			history.pushState(null, '');
		}
		history.pushState(null, '');
		window.addEventListener('popstate', onpop);
		return () => window.removeEventListener('popstate', onpop);
	});

	// where the remote starts on a new page: on what there is to watch. Left to
	// the document, focus begins at the top of the frame and the first press of
	// down opens the account menu instead of reaching the posters.
	$effect(() => {
		page.url.pathname;
		if (!surface.isTv || !me.open || !watching.profile) return;
		// pressed in the menu: the remote stays there, and right is the way in. A
		// ring already standing on the shelf is one OK away from starting a film
		// that was only being looked at.
		if (preview.landed()) return;
		// The remote starts on what there is to watch, because that is what you
		// came to the page for. Not on `/`, which a television only passes
		// through on its way to a section: landing in the menu there leaves that
		// section's head on the screen of the one it goes on to.
		// Where the ring actually was on this path, if it has been here before:
		// what was focused, whatever it was, rather than a selector rebuilt from
		// the address, which works only while the thing opened is a card with an
		// id in the URL.
		if (page.url.pathname === '/') return;
		// The first time on a section the ring is in the menu, on that section,
		// and right is the way in — as it is when the section was pressed there.
		// A page been on before takes the ring back to what it was left on.
		if (nav.level === 1 && !nav.perch()) return focusWaiting('nav.rail a.in');
		// What the page is about before the chrome that introduces it: a poster,
		// then anything to press that is not in the head — the name of whoever
		// directed a series is a detour, its first season is not. Last of all,
		// anything at all, because a page whose only controls are in its head is
		// still a page the arrows have to work on. A page that knows better says
		// so with `data-lands`, and the chosen thing inside it goes first: a series
		// lands on the season it is in, not on season one.
		return nav.land([
			'main [data-lands] :is(button, a[href]).on',
			'main [data-lands] :is(button, a[href])',
			'.card',
			'main :is(button, a[href]):not(header *, .head *)',
			'main :is(button, a[href])'
		]);
	});
}
