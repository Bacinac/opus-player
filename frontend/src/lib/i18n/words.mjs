#!/usr/bin/env node
// Every word this module says, checked rather than remembered — by the
// package's checker, with the families only this module knows. Each family
// names where its members come from, and a built key from a family nobody
// declared fails here rather than on the screen.
//
// It spans both halves of the repository, because half of what the screens say
// is a vocabulary the backend owns. So it runs over the repo rather than inside
// the frontend container: `./check.sh`.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { checkWords, quotedIn, report } from '../kit/words/check.mjs';

// This file sits at <root>/frontend/src/lib/i18n/.
const ROOT = join(new URL('.', import.meta.url).pathname, '../../../..');
const read = (p) => readFileSync(join(ROOT, p), 'utf8');

function sources(dir) {
	return readdirSync(join(ROOT, dir)).flatMap((entry) => {
		if (entry === 'kit' || entry === 'opus' || entry === 'node_modules') return [];
		const path = join(dir, entry);
		if (statSync(join(ROOT, path)).isDirectory()) return sources(path);
		return /\.(svelte|ts)$/.test(entry) ? [path] : [];
	});
}

function ways() {
	const out = {};
	for (const [, key, inside] of read('frontend/src/lib/say/ways.ts').matchAll(/^\t(\w+): \[([^\]]*)\]/gm)) {
		out[key] = [...(out[key] ?? []), ...[...inside.matchAll(/'([^']+)'/g)].map((m) => m[1])];
	}
	return out;
}

// the token home automation calls with is shown by its own card, not the form
const spec = () =>
	[...read('backend/opus/settings_store.py').matchAll(/SettingSpec\("(\w+)",\s*"(\w+)"/g)]
		.map((m) => ({ key: m[1], group: m[2] }))
		.filter((s) => s.group !== 'access');
const groups = () => [...new Set(spec().map((s) => s.group))];
const captions = (list) => () =>
	quotedIn(ROOT, 'frontend/src/lib/keep/captions.svelte.ts', new RegExp(`${list}: \\w+\\[\\] = \\[([^\\]]*)\\]`));

const families = {
	surface: {
		where: 'SURFACES in keep/surface.svelte.ts',
		members: () => quotedIn(ROOT, 'frontend/src/lib/keep/surface.svelte.ts', /SURFACES: Surface\[\] = \[([^\]]*)\]/)
	},
	'captions.sizes': { where: 'CAPTION_SIZES in keep/captions.svelte.ts', members: captions('CAPTION_SIZES') },
	'captions.places': { where: 'CAPTION_PLACES in keep/captions.svelte.ts', members: captions('CAPTION_PLACES') },
	'captions.backdrops': {
		where: 'CAPTION_BACKDROPS in keep/captions.svelte.ts',
		members: captions('CAPTION_BACKDROPS')
	},
	// the whole shelf is a page too, and is named by the wall family
	// what the catalogue offers is named by the plugin that opens it
	find: {
		where: 'WAYS and PAGES in say/ways.ts, less offered',
		members: () => [...new Set(Object.values(ways()).flat())].filter((w) => w !== 'all' && w !== 'offered')
	},
	row: {
		where: 'the sections in say/ways.ts, and the rows home.py and explore.py build',
		members: () => [
			...Object.keys(ways()),
			'home',
			...[...read('backend/opus/api/routers/home.py').matchAll(/\{"key": "(\w+)"/g)].map((m) => m[1]),
			...[...read('backend/opus/api/routers/explore.py').matchAll(/^\s{8}"(\w+)": \("/gm)].map((m) => m[1])
		]
	},
	shelf: {
		where: 'ORDERS and Way in keep/shelf.svelte.ts',
		members: () => {
			const path = 'frontend/src/lib/keep/shelf.svelte.ts';
			const dirs = quotedIn(ROOT, path, /type Way = ([^;]*);/);
			return quotedIn(ROOT, path, /ORDERS = \[([^\]]*)\]/).flatMap((order) => dirs.map((way) => `${order}.${way}`));
		}
	},
	wall: {
		where: 'SHELVES in keep/shelf.svelte.ts',
		members: () => quotedIn(ROOT, 'frontend/src/lib/keep/shelf.svelte.ts', /SHELVES = \[([^\]]*)\]/)
	},
	field: { where: 'SETTINGS_SPEC in backend/opus/settings_store.py', members: () => spec().map((s) => s.key) },
	'settings.group': { where: 'the groups of SETTINGS_SPEC in backend/opus/settings_store.py', members: groups },
	'settings.hint': { where: 'the groups of SETTINGS_SPEC in backend/opus/settings_store.py', members: groups },
	storage: {
		// Not ours: the Library reports what each disk holds, one word per
		// configured directory. Written out because the owner is another
		// repository, and checked all the same.
		where: 'DIR_KEYS in the Library (opus-library, backend/opus/settings_store.py)',
		members: () => ['music', 'movies', 'tv', 'video', 'photos', 'landing']
	},
	award: {
		where: 'the bodies of AWARDS in the Library (opus-library, backend/opus/video/metadata/awards.py)',
		members: () => ['oscar', 'palme_dor', 'golden_lion', 'golden_bear', 'bafta', 'emmy', 'golden_globe']
	},
	count: {
		// every kind is painted in say/count.ts or named where it is counted; a
		// shelf's kinds reach count() through tables whose kinds are all painted
		where: 'LOOK in say/count.ts, and the kinds count() is called with',
		members: () =>
			[
				...[...read('frontend/src/lib/say/count.ts').matchAll(/^\t(\w+): \{ (?:tone|kind):/gm)].map((m) => m[1]),
				...sources('frontend/src').flatMap((path) =>
					[...read(path).matchAll(/\bcount\([^,()]+(?:\([^()]*\))?[^,()]*,\s*'(\w+)'\)/g)].map((m) => m[1])
				)
			].flatMap((kind) => ['one', 'few', 'many'].map((form) => `${kind}.${form}`))
	},
	genre: {
		// TMDB's list, not ours: genre.ts reads the key back out of `t()` and
		// falls through to the English name for a genre with no word here
		where: "TMDB's genres, which say/genre.ts falls through to English for",
		open: true
	},
	'music.genre': {
		// Deezer's list by its English name: musicGenreName() reads the key back
		// out of `t()` and falls through to Deezer's word for one not here
		where: "Deezer's genres, which say/genre.ts falls through to Deezer's name for",
		open: true
	}
};

report(checkWords({ root: ROOT, packages: ['frontend/src/lib/kit', 'frontend/src/lib/opus'], families, leftovers: true }));
