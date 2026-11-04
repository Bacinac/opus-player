/* In-browser synthetic API for the public OPUS Player demo.
 *
 * The household is Library's demo catalogue, copied in when the demo is built:
 * the Player shows the same films, records and photographs through its own
 * screens, as an installed Player shows what its Library holds.
 */
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
	// the roster's people, each with the face the library says they are
	const profile = { key: 'demo', name: 'Nora', colour: '#cf765f', face: 501, audio_languages: 'hr,en', subtitle_languages: 'hr,en', screensaver: '' };
	const people = [profile,
		{ key: 'bruno', name: 'Bruno', colour: '#4f8e9b', face: 502, audio_languages: 'hr,en', subtitle_languages: 'hr,en', screensaver: 'household' },
		{ key: 'mia', name: 'Mia', colour: '#8f7ac2', face: 503, audio_languages: 'en,hr', subtitle_languages: 'en,hr', screensaver: '' },
		{ key: 'toma', name: 'Toma', colour: '#7a9b4f', face: 504, audio_languages: 'hr', subtitle_languages: 'hr', screensaver: 'cameras' }];

	let loading;
	function catalogue() {
		loading ??= realFetch('/demo-fixtures.json', { cache: 'no-store' })
			.then((r) => {
				if (!r.ok) throw new Error(`demo fixtures: ${r.status}`);
				return r.json();
			})
			.then(shape);
		return loading;
	}

	// Library's rows, as the Player's backend turns them into cards
	function shape(d) {
		const director = (names) => names.map((name, i) => ({ id: i + 1, name }));
		const releases = Object.values(d.artist_details).flatMap((a) => a.releases.map((r) => ({ ...r, artist: a })));
		const movie = (m) => ({
			kind: 'movie', id: m.id, title: m.title, subtitle: m.year, year: m.year, image: m.poster_url, backdrop: m.backdrop_url,
			state: m.status, overview: m.overview, runtime_min: m.runtime_min, genres: m.genres, directors: director(m.directors)
		});
		const show = (row) => {
			const s = d.series_details[row.id];
			return {
				kind: 'series', id: row.id, title: row.title, subtitle: row.year, year: row.year, image: row.poster_url, backdrop: s.backdrop_url,
				state: 'complete', overview: s.overview, episodes: row.episodes_total, seen: 1
			};
		};
		const artist = (a) => ({
			kind: 'artist', id: a.id, title: a.name, subtitle: null, image: a.image_url, backdrop: a.image_url,
			state: 'complete', overview: a.bio, round: true, country: a.country, releases: a.releases.length,
			held: a.releases.filter((r) => r.status === 'complete').length
		});
		const album = (r) => ({
			kind: 'music', id: r.id, title: r.title, subtitle: `${r.artist.name} · ${r.release_date.slice(0, 4)}`, artist: r.artist.name, album: r.title,
			image: r.cover_url, backdrop: r.cover_url, state: r.status, overview: `${r.track_count} tracks, ${r.quality?.codec ?? 'FLAC'}.`, square: true, holds: 'album'
		});
		const tracks = releases.flatMap((r) => d.tracks[r.id].tracks.map((t) => ({
			id: t.id, position: t.position, title: t.title, artist: r.artist.name, album: r.title, cover_url: r.cover_url,
			duration_s: t.duration_sec, release_id: r.id, channels: r.quality?.channels ?? 2, codec: r.quality?.codec ?? 'FLAC'
		})));
		const about = (m) => {
			const f = d.movie_details[m.id]?.files[0];
			return {
				overview: m.overview,
				file: f ? { resolution: f.resolution, video_codec: f.video_codec, container: f.container, size: f.size, duration_s: m.runtime_min * 60, audio: [{ lang: 'en', codec: 'EAC3', channels: 6 }], subtitles: f.subtitles.map((s) => s.lang) } : null,
				studios: [{ id: 1, name: m.studio }], year: m.year, runtime_min: m.runtime_min, genres: m.genres, directors: director(m.directors), cast: []
			};
		};
		const tree = (row) => {
			const s = d.series_details[row.id];
			return {
				id: s.id, tmdb_id: 9000 + s.id, title: s.title, year: s.year, overview: s.overview, backdrop: s.backdrop_url, image: s.poster_url,
				about: { overview: s.overview, file: null, studios: [{ id: 1, name: 'Blender Foundation' }], year: s.year, runtime_min: 3, genres: ['Comedy', 'Animation'], directors: director([s.director]), cast: [] },
				seasons: s.seasons.map((x) => ({ number: x.number, followed: true, episodes: x.episodes.map((e) => ({
					kind: 'episode', id: e.id, number: e.number, title: e.title, overview: e.overview, still: e.still_url, state: e.status, playable: true,
					resolution: e.file?.resolution ?? null, size: 412000000, subs: e.present_subs, missing_subs: e.missing_subs, air_date: e.air_date, runtime_min: 3
				})) }))
			};
		};
		const movies = d.movies.map(movie);
		const sintel = movies.find((m) => m.title === 'Sintel');
		const trees = Object.fromEntries(d.series.map((row) => [row.id, tree(row)]));
		return {
			movies, shows: d.series.map(show), artists: Object.values(d.artist_details).map(artist),
			albums: releases.filter((r) => r.status === 'complete').map(album), tracks, trees,
			about: {
				movie: Object.fromEntries(d.movies.map((m) => [m.id, about(m)])),
				series: Object.fromEntries(Object.entries(trees).map(([id, t]) => [id, t.about]))
			},
			releases: Object.fromEntries(releases.map((r) => [r.id, { id: r.id, title: r.title, artist: r.artist.name, cover_url: r.cover_url, release_date: r.release_date, tracks: tracks.filter((t) => t.release_id === r.id) }])),
			shelves: Object.fromEntries(Object.values(d.artist_details).map((a) => [a.id, {
				id: a.id, name: a.name, image: a.image_url,
				releases: a.releases.filter((r) => r.status === 'complete').map((r) => ({ id: r.id, title: r.title, year: r.release_date.slice(0, 4), cover: r.cover_url, tracks: r.track_count })),
				missing: a.releases.filter((r) => r.status !== 'complete').map((r) => ({ id: r.id, title: r.title, year: r.release_date.slice(0, 4), cover: r.cover_url, coming: false, state: r.status, progress: r.progress ?? 0 })),
				releases_total: a.releases.length, bio: a.bio, country: a.country, begin_year: a.begin_year, end_year: a.end_year, artist_type: a.artist_type, members: [], groups: []
			}])),
			resume: { ...sintel, position_s: 412, duration_s: sintel.runtime_min * 60 },
			photos: d.photos, people: d.people, lives: d.lives,
			placeOf: (id) => d.places.find((p) => p.key === d.photo_places[id]),
			places: d.places.map(({ place, country, photographs, at }) => ({ place, country, photographs, at })),
			episodes: Object.values(trees).flatMap((t) => t.seasons.flatMap((s) => s.episodes))
		};
	}

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
		return { box: 1, listening: true, transport: onTv.since === null ? 'paused' : 'playing', kind: onTv.kind, item_id: onTv.id, title: onTv.title, artist: onTv.subtitle, cover_url: onTv.cover, position, duration: onTv.duration, photo: photoOnTv };
	};
	// The quiz asks only what the demo knows of a photograph — where it was taken,
	// in which year, which of two came first — and marks it as the server does.
	const rounds = new Map();
	const standing = [
		{ key: 'demo', name: 'Nora', colour: '#cf765f', rounds: 3, points: 2140, best: 960, right: 22, asked: 30 },
		{ key: 'bruno', name: 'Bruno', colour: '#4f8e9b', rounds: 2, points: 1310, best: 780, right: 13, asked: 20 },
		{ key: 'mia', name: 'Mia', colour: '#8f7ac2', rounds: 1, points: 690, best: 690, right: 7, asked: 10 }];
	function quiz(h, count) {
		const shuffled = (list) => list.map((x) => [Math.random(), x]).sort((a, b) => a[0] - b[0]).map(([, x]) => x);
		const picture = (p) => ({ id: p.id, w: p.w, h: p.h, hash: p.hash, turn: 0 });
		const facts = (p) => ({ taken_at: p.taken_at, place: h.placeOf(p.id)?.place ?? null, country: h.placeOf(p.id)?.country ?? null, people: [] });
		const year = (p) => Number(p.taken_at.slice(0, 4));
		const places = [...new Set(h.places.map((p) => p.place))];
		const photos = shuffled(h.photos.filter((p) => p.kind === 'image' && h.placeOf(p.id)));
		const questions = [];
		for (const p of photos) {
			if (questions.length >= count) break;
			const n = questions.length + 1;
			const kind = ['where', 'when', 'order'][n % 3];
			if (kind === 'where') {
				const here = h.placeOf(p.id).place;
				const options = shuffled([here, ...shuffled(places.filter((x) => x !== here)).slice(0, 3)]).map((x) => ({ key: `l${x}`, label: x }));
				questions.push({ n, kind, photo: picture(p), options, answer: `l${here}`, facts: facts(p) });
			} else if (kind === 'when') {
				const y = year(p);
				const wrong = shuffled([-4, -3, -2, -1, 1, 2].map((d) => y + d).filter((x) => x <= 2026)).slice(0, 3);
				const options = [y, ...wrong].sort((a, b) => a - b).map((x) => ({ key: `y${x}`, label: String(x) }));
				questions.push({ n, kind, photo: picture(p), options, answer: `y${y}`, facts: facts(p) });
			} else {
				const other = photos.find((q) => year(q) !== year(p));
				if (!other) continue;
				questions.push({ n, kind, photo: picture(p), second: picture(other), options: [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }],
					answer: p.taken_at < other.taken_at ? 'a' : 'b', facts: facts(p), second_facts: facts(other) });
			}
		}
		return questions;
	}
	function game(h, path, method, body) {
		if (path === '/api/game/scores') return answer({ standing: clone(standing).sort((a, b) => b.points - a.points), me: 'demo' });
		if (path === '/api/game/rounds' && method === 'POST') {
			const id = rounds.size + 1;
			const questions = quiz(h, Math.min(Number(body.count) || 10, 10));
			rounds.set(id, { questions, started: {}, total: 0, streak: 0 });
			return answer({ id, seconds: 20, questions: questions.map(({ answer: _, facts: __, second_facts: ___, ...q }) => q) }, 201);
		}
		let match = path.match(/^\/api\/game\/rounds\/(\d+)\/(start|answer)$/);
		if (match && rounds.has(Number(match[1]))) {
			const round = rounds.get(Number(match[1]));
			const n = Number(body.n);
			if (match[2] === 'start') {
				round.started[n] = Date.now();
				return answer({ seconds: 20 });
			}
			const q = round.questions[n - 1];
			const elapsed = (Date.now() - (round.started[n] ?? Date.now())) / 1000;
			const right = body.key === q.answer;
			round.streak = right ? round.streak + 1 : 0;
			const left = Math.max(0, Math.min(1, (20 - elapsed) / 20));
			const points = right ? Math.round((100 + 100 * left) * Math.min(1 + 0.2 * Math.max(round.streak - 1, 0), 2)) : 0;
			round.total += points;
			const done = n === round.questions.length;
			if (done) {
				const me = standing.find((s) => s.key === 'demo');
				Object.assign(me, { rounds: me.rounds + 1, points: me.points + round.total, best: Math.max(me.best, round.total), asked: me.asked + round.questions.length });
			}
			if (right) standing.find((s) => s.key === 'demo').right++;
			return answer({ n, right, seconds: elapsed, points, correct: q.answer, facts: q.facts, second_facts: q.second_facts, total: round.total, streak: round.streak, done });
		}
		// together needs phones on the same house; the demo opens the lobby and nobody comes
		const lobby = { id: 1, seconds: 20, count: 10, host: { key: 'demo', name: 'Nora', colour: '#cf765f' }, mine: 'host', me: 'demo', n: null, left: null, revealed: false, done: false, question: null, players: [] };
		if (path === '/api/game/parties' && method === 'POST') return answer(lobby, 201);
		if (path === '/api/game/parties') return answer([]);
		match = path.match(/^\/api\/game\/parties\/\d+$/);
		if (match) return answer(method === 'DELETE' ? {} : lobby);
		return null;
	}
	async function api(path, method, url, input, init) {
		const body = await bodyOf(input, init);
		const h = await catalogue();
		if (path === '/api/version') return realFetch('/demo-version.json', { cache: 'no-store' });
		if (path === '/api/auth/session') return answer({ required: true, authenticated: true, box: '', username: 'demo', role: 'admin', person: 'demo', album: true, shelf_orders: '{}', profile: { key: profile.key, name: profile.name, colour: profile.colour } });
		if (path === '/api/auth/login' || path === '/api/auth/logout' || path === '/api/auth/password') return answer({ ok: true });
		if (path === '/api/auth/token') return answer({ token: method === 'POST' ? 'opus_demo_new_token' : 'opus_demo_service_token' });
		if (path === '/api/auth/people') return answer({ people: [
			{ name: 'demo', display: 'Demo administrator', role: 'admin', disabled: false, person_id: null, circle: [] },
			{ name: 'obitelj', display: 'Family member', role: 'user', disabled: false, person_id: 42, circle: [] },
			{ name: 'gost', display: 'Guest', role: 'guest', disabled: false, person_id: null, circle: [45, 46] }
		] });
		if (path === '/api/auth/devices') return answer({ devices: [
			{ id: 1, name: 'OPUS TV · living room', module: 'player', collected: true, let_in_by: 'demo', let_in_at: '2026-09-01T18:00:00Z', seen_at: '2026-09-19T09:15:00Z', app: 'v1.0.65', person: null },
			{ id: 2, name: 'Guest room', module: 'player', collected: true, let_in_by: 'demo', let_in_at: '2026-09-12T16:30:00Z', seen_at: '2026-09-18T21:05:00Z', app: 'v1.0.64', person: 'gost' }
		] });
		if (path === '/api/auth/cars') return answer({ cars: [{ id: 1, name: 'Family car', seen_at: '2026-09-18T17:20:00Z' }] });
		if (path.startsWith('/api/auth/')) return answer({ ok: true });
		if (path === '/api/users' && method === 'GET') return answer(clone(people));
		if (/^\/api\/users\/[^/]+\/pick$/.test(path)) return answer({ ok: true, profile });
		if (/^\/api\/users\//.test(path)) return answer({ ok: true });
		const owned = h.movies.filter((m) => m.state !== 'downloading');
		const playing = h.tracks.find((t) => t.album === 'Svjetla na rivi' && t.position === 2);
		const listening = { kind: 'track', id: playing.id, title: playing.title, subtitle: playing.artist, image: playing.cover_url, backdrop: playing.cover_url, state: 'complete', overview: '', square: true, release_id: playing.release_id, position_s: 87, duration_s: playing.duration_s };
		if (path === '/api/home') {
			return answer({ rows: [
				{ key: 'continue', cards: [h.resume, listening] },
				{ key: 'movies', cards: owned }, { key: 'series', cards: h.shows }, { key: 'music', cards: [...h.albums, ...h.artists] }
			] });
		}
		if (path === '/api/rows/music') {
			const fresh = [...h.albums].sort((a, b) => h.releases[b.id].release_date.localeCompare(h.releases[a.id].release_date));
			return answer({ rows: [
				{ key: 'listening', cards: [listening] },
				{ key: 'most_heard', cards: [...h.artists].reverse() },
				{ key: 'just_in', cards: fresh }
			] });
		}
		if (path.startsWith('/api/rows/')) return answer({ rows: [] });
		if (path === '/api/shelves') {
			const span = (list) => [Math.min(...list), Math.max(...list)];
			return answer({
				movies: { count: owned.length, hours: Math.round(owned.reduce((n, m) => n + m.runtime_min, 0) / 60), span: span(owned.map((m) => m.year)) },
				series: { count: h.shows.length, episodes: h.episodes.length, hours: Math.round(h.episodes.length * 3 / 60), span: span(h.shows.map((s) => s.year)) },
				music: { count: h.artists.length, releases: h.albums.length, hours: Math.round(h.tracks.reduce((n, t) => n + t.duration_s, 0) / 3600), span: span(Object.values(h.releases).map((r) => Number(r.release_date.slice(0, 4)))) },
				photos: { count: h.photos.length, people: h.people.length, places: h.places.length, span: span(h.photos.map((p) => Number(p.taken_at.slice(0, 4)))) }
			});
		}
		if (path === '/api/library/movies') return answer(clone(owned));
		if (path === '/api/library/series') return answer(clone(h.shows));
		if (path === '/api/library/music') return answer(clone(h.artists));
		let match = path.match(/^\/api\/library\/series\/(\d+)/);
		if (match) return answer(clone(h.trees[match[1]] ?? Object.values(h.trees)[0]));
		const record = (r) => ({ overview: `${r.title} by ${r.artist}, a fictional record in the demo catalogue.`, year: Number(r.release_date.slice(0, 4)), genres: [], runtime_min: Math.round(r.tracks.reduce((n, t) => n + t.duration_s, 0) / 60), directors: [], cast: [] });
		match = path.match(/^\/api\/library\/about\/([a-z]+)\/(\d+)/);
		if (match) {
			const kind = match[1] === 'episode' ? 'series' : match[1];
			if (h.about[kind]) return answer(clone(h.about[kind][match[2]] ?? Object.values(h.about[kind])[0]));
			const shelf = h.shelves[match[2]];
			if (kind === 'artist' && shelf) return answer({ overview: shelf.bio, year: shelf.begin_year, genres: [], runtime_min: null, directors: [], cast: [] });
			return answer(record(h.releases[match[2]] ?? Object.values(h.releases)[0]));
		}
		match = path.match(/^\/api\/library\/artist\/(\d+)/);
		if (match) return answer(clone(h.shelves[match[1]] ?? Object.values(h.shelves)[0]));
		match = path.match(/^\/api\/library\/release\/(\d+)(\/about)?$/);
		if (match) {
			const r = h.releases[match[1]] ?? Object.values(h.releases)[0];
			return answer(match[2] ? record(r) : clone(r));
		}
		if (/^\/api\/progress\/watched\//.test(path)) return answer({ watched: [h.episodes[0].id], partly: { [h.episodes[1].id]: 0.38 } });
		if (/^\/api\/progress\//.test(path)) return answer({ position_s: 6, watched: false });
		if (path === '/api/progress') return answer({ ok: true });
		if (path === '/api/music/favorites') return answer({ tracks: clone(h.tracks.filter((t) => t.position === 2).slice(0, 5)) });
		if (path.startsWith('/api/music/favorites/')) return answer({ ok: true });
		if (path === '/api/radio/stations') return answer({ stations: [{ kind: 'station', id: 1, title: 'Radio Obala', subtitle: 'Coastal sounds, all day', image: h.artists[0].image, backdrop: null, state: null, overview: '', url: 'https://example.invalid/radio', play_url: '', square: true }] });
		if (path === '/api/explore/ways') return answer({ music: [] });
		if (path === '/api/words') return answer({ hr: {}, en: {} });
		if (path === '/api/explore' || path === '/api/explore/music') return answer({ rows: [{ key: 'trending', cards: [...owned].reverse() }] });
		if (path.startsWith('/api/explore/want')) return answer({ added: true, name: 'Demo content' });
		// the world's winners come from TMDB, which a demo does not reach; none of its films won one
		if (path === '/api/explore/awarded') return answer({ awards: [], cards: [] });
		if (path.startsWith('/api/explore/')) return answer([]);
		if (path === '/api/photos/timeline/buckets') {
			const months = [];
			for (const p of h.photos) {
				const month = p.taken_at.slice(0, 7);
				if (months.at(-1)?.month === month) months.at(-1).count++;
				else months.push({ month, count: 1 });
			}
			return answer({ months, total: h.photos.length, undated: 0 });
		}
		if (path === '/api/photos/timeline') return answer({ photos: clone(h.photos), next: null });
		if (path === '/api/photos/people') return answer(clone(h.people));
		if (path === '/api/photos/places') return answer(clone(h.places));
		if (path === '/api/photos/onthisday') return answer({ years: [2025, 2024, 2023].map((y) => {
			const shots = h.photos.filter((p) => p.taken_at.startsWith(String(y))).slice(0, 4);
			const people = h.lives.filter((l) => l.person && l.years[0] <= y && y <= l.years[1]).map((l) => ({ id: l.person.id, name: l.person.name, faces: 2 }));
			return { year: y, people, cover: shots[0].id, photographs: clone(shots) };
		}) });
		match = path.match(/^\/api\/photos\/(demo-\d+)$/);
		if (match) {
			const p = h.photos.find((x) => x.id === match[1]) ?? h.photos[0];
			return answer({ id: p.id, kind: p.kind, taken_at: p.taken_at, place: h.placeOf(p.id)?.place ?? null, faces: [] });
		}
		if (path === '/api/photos/vault/keys') return answer({ keys: [] });
		if (path === '/api/photos/vault/stat') return answer({ files: 0, bytes: 0 });
		if (path.startsWith('/api/photos/vault')) return answer({ items: [], next: null });
		if (path.startsWith('/api/game/')) {
			const said = game(h, path, method, body);
			if (said) return said;
		}
		if (path === '/api/tv/boxes') return answer({ boxes: [{ id: 1, name: 'Living room', listening: true, house: true, wakes: true }] });
		if (path === '/api/tv/now') return answer(tvNow());
		// the television's mailbox: the house sends it nothing in a demo, so it waits as the real one does
		if (path === '/api/tv/inbox') {
			await new Promise((resolve) => setTimeout(resolve, 25000));
			return answer({ boot: 'demo', seq: 0, order: null, control: null });
		}
		if (path === '/api/tv/open' && method === 'POST') {
			const found = h.movies.find((m) => m.id === body.id);
			const episode = h.episodes.find((e) => e.id === body.id);
			const series = Object.values(h.trees)[0];
			showOnTv(null);
			tell({ kind: body.kind, id: body.id, title: found ? found.title : series.title, subtitle: found ? String(found.year) : `S1E${episode?.number ?? 1}`, cover: found ? found.image : series.image, duration: (found?.runtime_min ?? 3) * 60, at: body.at || 0, since: Date.now() });
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
		if (path === '/api/cast/boxes' && method === 'GET') return answer({ sources: ['MUSIC', 'SHIELD', 'GAME'], boxes: [{ id: 1, name: 'Living room', source: 'SHIELD', wired_on: 'Marantz SR6015', sink: 'Marantz SR6015' }] });
		if (path === '/api/cast/state') return answer({ transport: 'stopped', title: '', artist: '', album: '', source: null, position: null, duration: null, index: null, volume: 42, mute: false });
		if (path.startsWith('/api/cast/') || path === '/api/tv/state') return answer({ ok: true });
		if (path === '/api/storage') return answer({ volumes: [{ holds: ['movies', 'series'], path: '/media/video', total: 8000000000000, used: 4600000000000, free: 3400000000000 }, { holds: ['music', 'photos'], path: '/media/archive', total: 4000000000000, used: 1700000000000, free: 2300000000000 }] });
		if (path === '/api/settings') {
			if (method === 'PUT') settings = settings.map((s) => body[s.key] === undefined || s.secret ? s : { ...s, value: String(body[s.key]) });
			return answer(clone(settings));
		}
		if (path === '/api/app/apk.json' || path === '/api/app/music.json') return realFetch(path, { cache: 'no-store' });
		if (path === '/api/history' && method === 'GET') {
			const service = (name) => ({ service: name, account: name === 'listenbrainz' ? 'nora-kovac' : null, waiting: 0, unknown: 0, problem: '' });
			return answer({ simkl_ready: true, services: [service('listenbrainz'), service('simkl')] });
		}
		if (path.startsWith('/api/history/')) return answer({ ok: true });
		if (path === '/api/play/stats') return answer({ transcodes: [], limit: 2, gpu: 'Intel Arc A380', load: [0.4, 0.3, 0.3], cores: 8 });
		if (/^\/api\/play\//.test(path) && path.endsWith('/ticket')) return answer({ prefix: path.slice(0, -'ticket'.length), ticket: 'demo' });
		// every film, episode and song plays the demo's one clip, and says so: 20 seconds of Big Buck Bunny
		match = path.match(/^\/api\/play\/(movie|episode)\/(\d+)\/plan$/);
		if (match) {
			const about = h.about.movie[match[2]] ?? (match[1] === 'movie' ? h.about.movie[h.resume.id] : null);
			return answer({ title: 'Demo playback', mode: 'direct', width: 640, height: 360, codec: 'h264', kbps: 1620, duration_s: 20, subtitles: [],
				audio: [{ index: 0, lang: 'en', codec: 'aac', channels: 2, title: 'English' }], source: { container: 'mp4', video_codec: 'h264', width: 640, height: 360, frame_rate: 24 },
				chapters: [], year: about?.year, runtime_min: about?.runtime_min, details: about });
		}
		// a song plays the same clip, and its score has no words
		if (/^\/api\/play\/track\/\d+\/lyrics$/.test(path)) return answer({ source: '', instrumental: true, lines: [], plain: '' });
		// the road a demo has is the visitor's own to Cloudflare, which nothing here can measure honestly
		if (path === '/api/play/reach') return new Response(null, { status: 204 });
		return answer({ detail: `Demo fixture is missing ${method} ${path}` }, 404);
	}
	window.fetch = async function (input, init) {
		const url = new URL(input instanceof Request ? input.url : String(input), location.href);
		if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) return realFetch(input, init);
		return api(url.pathname, (init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase(), url, input, init);
	};
})();
