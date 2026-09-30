import type { QueueTrack } from '$lib/keep/queue.svelte';

export type Card = {
	kind: 'movie' | 'series' | 'episode' | 'artist' | 'music' | 'track' | 'station' | 'release';
	id: number;
	series_id?: number;
	tmdb_id?: number;
	// false on a card from Explore, whose `id` is TMDB's and means nothing to
	// the library; absent everywhere else, where the id is the library's own
	owned?: boolean;
	title: string;
	subtitle?: string | number | null;
	/** on an award wall: the years it won, under each award */
	won?: Record<string, number[]>;
	/** found in the world: the subscription services it is on. Absent while
	    the library is still looking it up. */
	streaming?: Service[] | null;
	image: string | null;
	backdrop: string | null;
	state: string | null;
	overview: string;
	badge?: string | null;
	round?: boolean;
	/** a record sleeve, which is square */
	square?: boolean;
	/** a station's stream, kept alive by somebody else, and where it is opened
	    from here */
	url?: string | null;
	play_url?: string | null;
	runtime_min?: number | null;
	/** whose record this is, on a card a catalogue offered */
	artist?: string;
	/** what an offered card can be opened to show: a mix, a playlist, an album */
	holds?: 'mix' | 'playlist' | 'album' | null;
	/** somebody rather than something. A person is never asked for. */
	person?: boolean;
	/** the record a card stands for, when it stands for one */
	album?: string;
	genres?: string[];
	directors?: Named[];
	// an artist's own facts, which is what the band says about them instead
	end_year?: number | null;
	country?: string | null;
	country_hr?: string | null;
	releases?: number;
	/** of those, the ones there is something to play */
	held?: number;
	/** of a series, how many episodes are here */
	episodes?: number;
	/** the record a song is on, which is what goes back on when it is picked */
	release_id?: number;
	/** whose record it is, on a card that stands for a record */
	artist_id?: number;
	/** how many of it this profile has finished — one for a film it has seen,
	    the count of episodes for a series. Another profile in the house has its
	    own number and never sees this one. */
	seen?: number;
	year?: number | null;
	position_s?: number;
	duration_s?: number | null;
	/** an episode card's place in its series, said into a line by `say/` */
	season_number?: number;
	number?: number;
	episode_title?: string;
};

export type Person = {
	id: number;
	name: string;
	character: string;
	profile_url: string | null;
};

export type FileFacts = {
	resolution?: string;
	video_codec?: string;
	container?: string;
	size?: number | null;
	duration_s?: number | null;
	audio?: { lang: string; codec: string; channels: number | null; profile?: string | null }[];
	subtitles?: string[];
};

/** A subscription service, and whether the house pays for it. */
export type Service = { id: number; name: string; logo: string | null; ours: boolean };

/** Named for a reader, numbered for the screen that answers "what else". */
export type Named = { id: number | null; name: string; logo?: string | null };

export type About = {
	overview: string;
	file?: FileFacts;
	studios?: Named[];
	year: number | null;
	runtime_min: number | null;
	genres: string[];
	directors: Named[];
	cast: Person[];
};

/** Somebody asked about, or some studio: who they are, above their work. */
export type Somebody = {
	name: string;
	about: string;
	image: string | null;
	born?: string | null;
	died?: string | null;
	from?: string;
};

export type Row = { key: string; cards: Card[]; label?: string };

export type Profile = {
	/** the name on the roster, or a local name for somebody who is on none.
	 *  One key space, because a local profile may not take a roster name. */
	key: string;
	name: string;
	colour: string;
	/** whether the roster is what says this person exists — and so whether they
	 *  can be removed here at all */
	roster?: boolean;
	audio_languages?: string;
	subtitle_languages?: string;
	/** whose photographs a box's screensaver shows while this profile is
	 *  picked: '' whoever the profile is, 'household', or a person's id */
	screensaver?: string;
};

export type EpisodeEntry = {
	kind: 'episode';
	id: number;
	number: number;
	title: string;
	overview?: string;
	state: string | null;
	playable: boolean;
	resolution: string | null;
	size?: number;
	subs?: string[];
	missing_subs?: string[];
	air_date: string | null;
	still?: string | null;
	runtime_min?: number | null;
};

export type ArtistShelf = {
	id: number;
	name: string;
	image: string | null;
	releases: { id: number; title: string; year: string; cover: string | null; tracks: number }[];
	/** the canonical records with nothing to play — what this artist is missing */
	missing: {
		id: number;
		title: string;
		year: string;
		cover: string | null;
		coming: boolean;
		/** what the library is doing about it, and how far it has got (0-1) */
		state: string | null;
		progress: number | null;
	}[];
	releases_total: number;
	bio: string;
	country: string | null;
	country_hr: string | null;
	begin_year: number | null;
	end_year: number | null;
	artist_type: string | null;
	members: { id: number; name: string }[];
	groups: { id: number; name: string }[];
};

export type ReleaseQueue = {
	id: number;
	title: string;
	artist: string;
	cover_url: string | null;
	release_date: string | null;
	tracks: QueueTrack[];
};

export type SeasonOffer = {
	title: string;
	in_library: boolean;
	library_id: number | null;
	seasons: { number: number; episodes: number; year: number | null }[];
};

/** A season as the lists render it: its episodes, and how much of it is here. */
export type SeasonView = {
	number: number;
	episodes: EpisodeEntry[];
	total: number;
	have: number;
	/** whether the library is still looking for what is missing from it. A
	    season nobody follows is ignored, and so is every line in it: "wanted" on
	    an episode nothing is looking for is a promise with nobody behind it. */
	followed?: boolean;
	overview?: string;
	poster?: string | null;
};

export type SeriesTree = {
	id: number;
	tmdb_id: number;
	title: string;
	year: number | null;
	overview: string;
	backdrop: string | null;
	image: string | null;
	about: About;
	seasons: {
		number: number;
		followed: boolean;
		overview?: string;
		poster?: string | null;
		episodes: EpisodeEntry[];
	}[];
};

/** A disk the media sits on, as the Library measures it. Folders that share a
    device are one volume: counting them per folder counts the same terabytes
    twice. */
export type Volume = {
	holds: string[];
	path: string;
	total: number;
	used: number;
	free: number;
};

export type PlanSubtitle = {
	id: number;
	lang: string;
	codec: string;
	title: string;
	external: boolean;
	forced: boolean;
};

export type PlanAudio = { index: number; lang: string; codec: string; channels: number | null; title: string };

/** How a film is about to be played, and what it is. */
export type Plan = {
	title: string;
	mode: 'direct' | 'remux' | 'transcode';
	width: number | null;
	height: number | null;
	duration_s: number | null;
	subtitles: PlanSubtitle[];
	audio: PlanAudio[];
	source: {
		container: string;
		video_codec: string;
		width: number;
		height: number;
		frame_rate?: number | null;
	};
	preferred?: { audio: string; subtitle: string };
	chapters?: { position: number; start_s: number; title: string }[];
	credits_s?: number | null;
	intro_s?: number | null;
	intro_end_s?: number | null;
	season_left?: number | null;
	next?: { id: number; season_number: number; number: number; title: string } | null;
	year?: number | null;
	runtime_min?: number | null;
	details?: {
		overview?: string;
		genres?: string[];
		directors?: string[];
		cast?: { id: number; name: string; character: string; profile_url: string | null }[];
	};
};

/** A track as the box's own engine reports it. */
export type EngineTrack = {
	index: number;
	lang: string;
	label: string;
	channels: number | null;
	codec: string;
	chosen: boolean;
};
