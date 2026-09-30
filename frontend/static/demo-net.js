/* In-browser synthetic API for the public OPUS Player demo. */
(function () {
	'use strict';

	// The public demo speaks English until the visitor picks a language.
	try {
		if (!localStorage.getItem('locale')) localStorage.setItem('locale', 'en');
	} catch {
		/* no storage */
	}
	const realFetch = window.fetch.bind(window);
	const clone = (value) => JSON.parse(JSON.stringify(value));
	const answer = (body, status = 200) => new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
	});
	const profile = { key: 'demo', name: 'Demo', colour: '#cf765f', roster: true, audio_languages: 'hr,en', subtitle_languages: 'hr,en', shelf_orders: '' };
	let people = [profile, { key: 'obitelj', name: 'Family', colour: '#4f8e9b', roster: true, audio_languages: 'hr,en', subtitle_languages: 'hr,en', shelf_orders: '' }];
	const movie = (id, title, year, more = {}) => ({ kind: 'movie', id, title, subtitle: year, year, image: '/demo/poster.svg', backdrop: '/demo/backdrop.svg', state: 'complete', overview: 'A synthetic demo film showing details, resume, subtitles and the choice of audio output.', runtime_min: 116, genres: ['Drama', 'Adventure'], directors: [{ id: 1, name: 'Iva Demo' }], ...more });
	const series = (id, title, year, more = {}) => ({ kind: 'series', id, title, subtitle: year, year, image: '/demo/poster.svg', backdrop: '/demo/backdrop.svg', state: 'complete', overview: 'A demo series with seasons, episode tracking and library state.', episodes: 6, seen: 2, ...more });
	const artist = (id, title, more = {}) => ({ kind: 'artist', id, title, subtitle: '3 releases', image: '/demo/square.svg', backdrop: '/demo/backdrop.svg', state: 'complete', overview: 'A demo artist from the OPUS music library.', round: true, country: 'HR', releases: 3, held: 2, ...more });
	const album = (id, title, more = {}) => ({ kind: 'music', id, title, subtitle: 'Jadranski Kolektiv · 2024', artist: 'Jadranski Kolektiv', album: title, image: '/demo/square.svg', backdrop: '/demo/backdrop.svg', state: 'complete', overview: 'A lossless release in the demo catalogue.', square: true, holds: 'album', ...more });
	const movies = [movie(101, 'Stardust Roads', 2025, { position_s: 1840, duration_s: 6960 }), movie(102, 'The Quiet Coast', 2026), movie(103, 'Northern Passage', 2024, { state: 'waiting_subtitles' }), movie(104, 'Night Ferry', 2023)];
	const shows = [series(201, 'Edge of the Sea', 2025), series(202, 'Archive 9', 2024, { episodes: 8, seen: 8 }), series(203, 'The Last Signal', 2026, { state: 'wanted', seen: 0 })];
	const artists = [artist(301, 'Jadranski Kolektiv'), artist(302, 'Lumen', { country: 'SI' }), artist(303, 'Sjeverni Val', { country: 'IS' })];
	const albums = [album(311, 'Svjetla na rivi'), album(312, 'Između otoka', { subtitle: 'Jadranski Kolektiv · 2026' })];
	const tracks = [
		{ id: 401, position: 1, title: 'Prvi trajekt', artist: 'Jadranski Kolektiv', album: 'Svjetla na rivi', cover_url: '/demo/square.svg', duration_s: 224, release_id: 311, channels: 2, codec: 'FLAC' },
		{ id: 402, position: 2, title: 'Svjetla na rivi', artist: 'Jadranski Kolektiv', album: 'Svjetla na rivi', cover_url: '/demo/square.svg', duration_s: 267, release_id: 311, channels: 2, codec: 'FLAC' },
		{ id: 403, position: 3, title: 'Bonaca', artist: 'Jadranski Kolektiv', album: 'Svjetla na rivi', cover_url: '/demo/square.svg', duration_s: 241, release_id: 311, channels: 2, codec: 'FLAC' }
	];
	const photos = ['demo-photo-1', 'demo-photo-2', 'demo-photo-3', 'demo-photo-4'].map((id, i) => ({ id, kind: i === 2 ? 'video' : 'image', taken_at: ['2026-08-17T18:42:00+02:00', '2026-08-16T17:10:00+02:00', '2025-09-19T12:20:00+02:00', '2024-09-19T11:30:00+02:00'][i], dated: 'exact', w: 1200, h: 800, hash: null, ready: true, undecodable: false }));
	const about = { overview: 'Synthetic demo content, safe to show in public.', file: { resolution: '2160p HDR', video_codec: 'HEVC', container: 'MKV', size: 18360985190, duration_s: 6960, audio: [{ lang: 'hr', codec: 'EAC3', channels: 6 }, { lang: 'en', codec: 'TrueHD', channels: 8 }], subtitles: ['hr', 'en'] }, studios: [{ id: 1, name: 'OPUS Demo Studio' }], year: 2025, runtime_min: 116, genres: ['Drama', 'Adventure'], directors: [{ id: 1, name: 'Iva Demo' }], cast: [{ id: 10, name: 'Ana Demo', character: 'Mara', profile_url: '/demo/face.svg' }] };
	const tree = { id: 201, tmdb_id: 9002, title: 'Edge of the Sea', year: 2025, overview: 'Six episodes about a community where the land meets the sea.', backdrop: '/demo/backdrop.svg', image: '/demo/poster.svg', about, seasons: [{ number: 1, followed: true, episodes: [
		{ kind: 'episode', id: 2101, number: 1, title: 'Tide', overview: 'Where it begins.', state: 'complete', playable: true, resolution: '1080p', size: 3221225472, subs: ['hr', 'en'], missing_subs: [], air_date: '2025-10-03' },
		{ kind: 'episode', id: 2102, number: 2, title: 'Lighthouse', overview: 'A signal from the open sea.', state: 'complete', playable: true, resolution: '1080p', size: 3006477107, subs: ['hr', 'en'], missing_subs: [], air_date: '2025-10-10' },
		{ kind: 'episode', id: 2103, number: 3, title: 'Squall', overview: 'A storm changes the plan.', state: 'waiting_subtitles', playable: true, resolution: '1080p', size: 3435973837, subs: ['en'], missing_subs: ['hr'], air_date: '2025-10-17' }
	]}] };
	const release = { id: 311, title: 'Svjetla na rivi', artist: 'Jadranski Kolektiv', cover_url: '/demo/square.svg', release_date: '2024-05-17', tracks };
	const artistShelf = { id: 301, name: 'Jadranski Kolektiv', image: '/demo/square.svg', releases: [{ id: 311, title: 'Svjetla na rivi', year: '2024', cover: '/demo/square.svg', tracks: 9 }, { id: 312, title: 'Između otoka', year: '2026', cover: '/demo/square.svg', tracks: 8 }], missing: [{ id: 313, title: 'Rani valovi', year: '2018', cover: '/demo/square.svg', coming: false, state: 'wanted', progress: 0 }], releases_total: 3, bio: 'A synthetic demo artist showing a discography and lossless playback.', country: 'HR', begin_year: 2014, end_year: null, artist_type: 'group', members: [], groups: [] };
	const setting = (key, group, value, kind = 'text', secret = false) => ({ key, label: key, group, kind, secret, options: [], value: secret ? '' : value, is_set: secret ? true : null });
	let settings = [
		setting('dida_url', 'dida', 'https://dida.demo.invalid'), setting('dida_username', 'dida', 'opus'), setting('dida_password', 'dida', 'set', 'text', true), setting('dida_panel_key', 'dida', '', 'text', true),
		setting('audio_output_stereo', 'audio', 'dac'), setting('audio_dac_name', 'audio', 'iFi Zen DAC'), setting('audio_output_multi', 'audio', 'tv'), setting('audio_volume_entity', 'audio', 'denon:marantz_main'), setting('audio_amp_entity', 'audio', 'denon:marantz_main'), setting('audio_amp_source', 'audio', 'MUSIC'), setting('audio_amp_source_multi', 'audio', 'SHIELD'), setting('tv_box', 'audio', '1', 'number'), setting('stream_base', 'audio', 'http://opus-player.lan:8098')
	];
	async function bodyOf(input, init) {
		const body = init && init.body !== undefined ? init.body : input instanceof Request ? await input.clone().text() : '';
		try { return typeof body === 'string' && body ? JSON.parse(body) : {}; } catch (_) { return {}; }
	}
	// the living room's television, which plays what it is sent and says so, and
	// goes on playing while the page is reloaded
	let onTv = null;
	try { onTv = JSON.parse(sessionStorage.getItem('opus-demo-tv') || 'null'); } catch (_) { onTv = null; }
	const tell = (next) => {
		onTv = next;
		try { sessionStorage.setItem('opus-demo-tv', JSON.stringify(next)); } catch (_) { /* a private window keeps it for this page only */ }
	};
	// …and the photograph a phone is showing on it
	let photoOnTv = null;
	try { photoOnTv = JSON.parse(sessionStorage.getItem('opus-demo-tv-photo') || 'null'); } catch (_) { photoOnTv = null; }
	const showOnTv = (id) => {
		photoOnTv = id;
		try { sessionStorage.setItem('opus-demo-tv-photo', JSON.stringify(id)); } catch (_) { /* a private window keeps it for this page only */ }
	};
	const tvNow = () => {
		if (!onTv) return { box: 1, listening: true, transport: 'idle', kind: null, item_id: null, title: '', artist: '', cover_url: null, position: null, duration: null, photo: photoOnTv };
		const position = Math.min(onTv.duration, onTv.at + (onTv.since === null ? 0 : (Date.now() - onTv.since) / 1000));
		return { box: 1, listening: true, transport: onTv.since === null ? 'paused' : 'playing', kind: onTv.kind, item_id: onTv.id, title: onTv.title, artist: onTv.subtitle, cover_url: '/demo/poster.svg', position, duration: onTv.duration, photo: photoOnTv };
	};
	async function api(path, method, url, input, init) {
		const body = await bodyOf(input, init);
		if (path === '/api/version') return realFetch('/demo-version.json', { cache: 'no-store' });
		if (path === '/api/auth/session') return answer({ required: true, authenticated: true, username: 'demo', role: 'admin', person: 'demo', profile });
		if (path === '/api/auth/login' || path === '/api/auth/logout' || path === '/api/auth/password') return answer({ ok: true });
		if (path === '/api/auth/token') return answer({ token: method === 'POST' ? 'opus_demo_new_token' : 'opus_demo_service_token' });
		if (path === '/api/auth/people') return answer({ people: [{ name: 'demo', display: 'Demo administrator', role: 'admin', disabled: false }, { name: 'obitelj', display: 'Family member', role: 'user', disabled: false }] });
		if (path === '/api/auth/devices') return answer({ devices: [{ id: 1, name: 'OPUS TV · living room', module: 'player', collected: true, seen_at: '2026-09-19T09:15:00Z' }] });
		if (path === '/api/auth/cars') return answer({ cars: [{ id: 1, name: 'Family car', seen_at: '2026-09-18T17:20:00Z' }] });
		if (path.startsWith('/api/auth/')) return answer({ ok: true });
		if (path === '/api/users' && method === 'GET') return answer(clone(people));
		if (path === '/api/users' && method === 'POST') { const made = { key: 'new-demo', name: body.name || 'New profile', colour: body.colour || '#777', roster: false }; people.push(made); return answer(made); }
		if (/^\/api\/users\/[^/]+\/pick$/.test(path)) return answer({ ok: true, profile });
		if (/^\/api\/users\//.test(path) && method === 'DELETE') { people = people.filter((p) => encodeURIComponent(p.key) !== path.split('/')[3]); return answer({ ok: true }); }
		if (/^\/api\/users\//.test(path)) return answer({ ok: true });
		if (path === '/api/home') return answer({ rows: [
			{ key: 'continue', cards: [movies[0], { kind: 'track', id: 402, title: 'Svjetla na rivi', subtitle: 'Jadranski Kolektiv', image: '/demo/square.svg', backdrop: '/demo/backdrop.svg', state: 'complete', overview: '', square: true, release_id: 311, position_s: 87, duration_s: 267 }] },
			{ key: 'movies', cards: movies }, { key: 'series', cards: shows }, { key: 'music', cards: [...artists, ...albums] }
		] });
		if (path === '/api/shelves') return answer({ movies: { count: 4, hours: 8, span: [2023, 2026] }, series: { count: 3, episodes: 17, span: [2024, 2026] }, music: { count: 3, releases: 6, span: [2018, 2026] }, photos: { count: 4, people: 2, places: 2, span: [2024, 2026] } });
		if (path === '/api/library/movies') return answer(clone(movies));
		if (path === '/api/library/series') return answer(clone(shows));
		if (path === '/api/library/music') return answer(clone(artists));
		if (path === '/api/library/series/201') return answer(clone(tree));
		if (/^\/api\/library\/series\//.test(path)) return answer(clone({ ...tree, id: Number(path.split('/').pop()) || 201 }));
		if (/^\/api\/library\/about\//.test(path)) return answer(clone(about));
		if (path === '/api/library/artist/301' || /^\/api\/library\/artist\//.test(path)) return answer(clone(artistShelf));
		if (path === '/api/library/release/311' || /^\/api\/library\/release\/\d+$/.test(path)) return answer(clone(release));
		if (/^\/api\/library\/release\/\d+\/about$/.test(path)) return answer({ overview: 'A lossless demo release.', year: 2024, genres: ['Electronic'], runtime_min: 38, directors: [], cast: [] });
		if (/^\/api\/progress\/watched\//.test(path)) return answer({ watched: [] });
		if (/^\/api\/progress\//.test(path)) return answer({ position_s: 1840, watched: false });
		if (path === '/api/progress') return answer({ ok: true });
		if (path === '/api/music/favorites') return answer({ tracks: clone(tracks.slice(0, 2)) });
		if (path.startsWith('/api/music/favorites/')) return answer({ ok: true });
		if (path === '/api/radio/stations') return answer({ stations: [{ kind: 'station', id: 1, title: 'Radio Demo', subtitle: 'Jadranski zvuk', image: '/demo/square.svg', backdrop: null, state: null, overview: '', url: 'https://example.invalid/radio', play_url: '', square: true }] });
		if (path === '/api/explore/ways') return answer({ music: [] });
		if (path === '/api/words') return answer({ hr: {}, en: {} });
		if (path === '/api/explore' || path === '/api/explore/music') return answer({ rows: [{ key: 'trending', cards: [movie(901, 'Demo Horizon', 2026, { owned: false }), series(902, 'The Last Signal', 2026, { owned: false, tmdb_id: 902 })] }] });
		if (path.startsWith('/api/explore/')) return answer([]);
		if (path === '/api/photos/timeline/buckets') return answer({ months: [{ month: '2026-08', count: 2 }, { month: '2025-09', count: 1 }, { month: '2024-09', count: 1 }], total: 4, undated: 0 });
		if (path === '/api/photos/timeline') return answer({ photos: clone(photos), next: null });
		if (path === '/api/photos/people') return answer([{ id: 41, name: 'Ana Demo', given_name: 'Ana', born_on: '1991-04-12', cover: 501, faces: 18, years: [2024, 2026] }, { id: 42, name: 'Marko Demo', given_name: 'Marko', born_on: '1989-09-21', cover: 502, faces: 11, years: [2025, 2026] }]);
		if (path === '/api/photos/places') return answer([{ place: 'Demo Bay', country: 'Croatia', photographs: 18, at: { lat: 43.5, lon: 16.4 } }, { place: 'Mountain Road', country: 'Slovenia', photographs: 7, at: { lat: 46.1, lon: 14.9 } }]);
		if (path === '/api/photos/onthisday') return answer({ years: [{ year: 2025, people: [{ id: 41, name: 'Ana Demo', faces: 2 }], cover: 'demo-photo-3', photographs: [photos[2]] }, { year: 2024, people: [{ id: 42, name: 'Marko Demo', faces: 1 }], cover: 'demo-photo-4', photographs: [photos[3]] }] });
		if (/^\/api\/photos\/demo-photo-\d+$/.test(path)) return answer({ id: path.split('/').pop(), kind: 'image', taken_at: '2026-08-17T18:42:00+02:00', place: 'Demo Bay', faces: [{ id: 501, person: { id: 41, name: 'Ana Demo' } }] });
		if (path === '/api/photos/vault/keys') return answer({ keys: [] });
		if (path === '/api/photos/vault/stat') return answer({ files: 0, bytes: 0 });
		if (path.startsWith('/api/photos/vault')) return answer({ items: [], next: null });
		if (path === '/api/tv/boxes') return answer({ boxes: [{ id: 1, name: 'Living room', listening: true, house: true, wakes: true }] });
		if (path === '/api/tv/now') return answer(tvNow());
		if (path === '/api/tv/open' && method === 'POST') {
			const found = movies.find((m) => m.id === body.id);
			showOnTv(null);
			tell({ kind: body.kind, id: body.id, title: found ? found.title : 'Edge of the Sea', subtitle: found ? String(found.year) : 'S1E1', duration: 6960, at: body.at || 0, since: Date.now() });
			return answer({ ok: true });
		}
		if (path === '/api/tv/photo' && method === 'POST') {
			if (body.id) tell(null);
			showOnTv(body.id || null);
			return answer({ ok: true });
		}
		if (path === '/api/tv/control' && method === 'POST') {
			const now = tvNow();
			if (onTv && body.command === 'play_pause') tell({ ...onTv, at: now.position, since: onTv.since === null ? Date.now() : null });
			if (onTv && body.command === 'seek') tell({ ...onTv, at: body.at, since: onTv.since === null ? null : Date.now() });
			if (body.command === 'stop') tell(null);
			return answer({ ok: true });
		}
		if (path === '/api/cast/outputs') return answer({ outputs: [{ id: 'browser', name: 'This browser' }, { id: 'stereo', entity: 'dac', name: 'iFi Zen DAC' }, { id: 'multi', entity: 'tv', name: 'OPUS TV · living room' }] });
		if (path === '/api/cast/options') return answer({ media: [{ value: 'dac', label: 'iFi Zen DAC' }, { value: 'denon:marantz_main', label: 'Living room · Marantz' }], sources: ['MUSIC', 'SHIELD'], boxes: [{ value: '1', label: 'OPUS TV · living room' }] });
		if (path === '/api/cast/state') return answer({ transport: 'stopped', title: '', artist: '', album: '', source: null, position: null, duration: null, index: null, volume: 42, mute: false });
		if (path.startsWith('/api/cast/') || path === '/api/tv/state') return answer({ ok: true });
		if (path === '/api/storage') return answer({ volumes: [{ holds: ['movies', 'series'], path: '/media/video', total: 8000000000000, used: 4600000000000, free: 3400000000000 }, { holds: ['music', 'photos'], path: '/media/archive', total: 4000000000000, used: 1700000000000, free: 2300000000000 }] });
		if (path === '/api/settings') {
			if (method === 'PUT') settings = settings.map((s) => body[s.key] === undefined || s.secret ? s : { ...s, value: String(body[s.key]) });
			return answer(clone(settings));
		}
		if (path === '/api/app/apk.json') return answer({ versionName: '0.1.444', bytes: 2442628 });
		if (path === '/api/app/music.json') return answer({ versionName: '0.1.448', bytes: 2298392 });
		if (path === '/api/play/stats') return answer({ active: 0, transcodes: 0 });
		if (/^\/api\/play\//.test(path) && path.endsWith('/ticket')) return answer({ prefix: path.slice(0, -'ticket'.length), ticket: 'demo' });
		if (/^\/api\/play\//.test(path) && path.endsWith('/plan')) return answer({ title: 'Demo playback', mode: 'direct', width: 3840, height: 2160, duration_s: 6960, subtitles: [{ id: 1, lang: 'hr', codec: 'srt', title: 'Croatian', external: true, forced: false }], audio: [{ index: 0, lang: 'hr', codec: 'eac3', channels: 6, title: 'Croatian 5.1' }], source: { container: 'mkv', video_codec: 'hevc', width: 3840, height: 2160 }, chapters: [], details: about });
		if (path.startsWith('/api/explore/want')) return answer({ added: true, name: 'Demo content' });
		return answer({ detail: `Demo fixture is missing ${method} ${path}` }, 404);
	}
	window.fetch = async function (input, init) {
		const url = new URL(input instanceof Request ? input.url : String(input), location.href);
		if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) return realFetch(input, init);
		return api(url.pathname, (init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase(), url, input, init);
	};
})();
