/* The guessing game, which is the archive asked back.
 *
 * A round is built by the backend out of what the library knows, and it arrives
 * whole — every question and every option, but never which option is right. The
 * answer is marked over there, one question at a time, because the clock that
 * scores it is over there too.
 *
 * Played together, the round is a party: one screen asks and holds the clock,
 * everybody else answers on a phone of their own, and the screen reveals. */

import { request } from '#lib/kit/index.js';

export type Kind = 'who' | 'where' | 'when' | 'missing' | 'zoom' | 'order' | 'age';

export type Option = {
	key: string;
	label: string;
};

export type Picture = { id: string; w: number; h: number; hash: string | null; turn: number };
export type Rect = { x: number; y: number; w: number; h: number };

export type Question = {
	n: number;
	kind: Kind;
	photo: Picture;
	options: Option[];
	/** the face being asked about, which is what a "who" question shows: the
	 *  photograph around it would answer the question for anybody who
	 *  recognises the room or who else is standing there */
	face?: number | null;
	/** the rectangle that face was cut out of, as fractions of the picture —
	 *  drawn over the whole photograph once the question has been answered, so
	 *  what is framed there is exactly the piece that was on the screen; for an
	 *  age question, drawn while it is asked, since the name is given and the
	 *  picture is whole */
	frame?: Rect | null;
	/** the patch over whoever is missing from a group, as fractions */
	hide?: Rect | null;
	/** where a detail starts, as fractions, and how far in */
	zoom?: { x: number; y: number; scale: number } | null;
	/** the other photograph, where two are asked about */
	second?: Picture | null;
	/** whose age is asked */
	name?: string | null;
};

export type Facts = {
	taken_at: string;
	place: string | null;
	country: string | null;
	people: { id: number; name: string }[];
};

export type Marked = {
	n: number;
	right: boolean;
	seconds: number;
	points: number;
	correct: string;
	facts: Facts;
	second_facts?: Facts;
	total: number;
	streak: number;
	done: boolean;
};

export type Round = { id: number; seconds: number; questions: Question[] };

export type Standing = {
	key: string;
	name: string;
	colour: string;
	rounds: number;
	points: number;
	best: number;
	right: number;
	asked: number;
};

export type Someone = { key: string; name: string; colour: string };

export type Player = Someone & {
	total: number;
	answered: boolean;
	picked: string | null;
	right: boolean | null;
	points: number | null;
};

export type Party = {
	id: number;
	seconds: number;
	count: number;
	host: Someone | null;
	mine: 'host' | 'player' | null;
	me: string;
	n: number | null;
	/** what is left of the clock, by the server's reckoning */
	left: number | null;
	revealed: boolean;
	done: boolean;
	question: Question | null;
	players: Player[];
	correct?: string;
	facts?: Facts;
	second_facts?: Facts;
	/** every question, handed to the host alone */
	questions?: Question[];
};

export type OpenParty = {
	id: number;
	host: Someone | null;
	players: number;
	under_way: boolean;
	mine: 'host' | 'player' | null;
};

const json = (body: unknown, method = 'POST'): RequestInit => ({
	method,
	headers: { 'content-type': 'application/json' },
	body: JSON.stringify(body)
});

/** How clearly a face was detected, which is the nearest thing to how hard it
 *  is to recognise. Three stops rather than a bar to drag: the game is played
 *  from a sofa as well, a remote cannot drag anything, and "0.79" says nothing
 *  to anybody. Each is measured — the pool of single-person photographs it
 *  leaves is 13,147 · 7,691 · 3,450. */
export const HARDNESS = { easy: 0.938, fair: 0.831, hard: 0.76 } as const;
export type Hardness = keyof typeof HARDNESS;

export const round = async (count = 10, how: Hardness = 'fair'): Promise<Round | null> =>
	request<Round>('/api/game/rounds', json({ count, hard: HARDNESS[how] }));

/** The question is on the screen now; this is where its clock starts. */
export const start = async (id: number, n: number): Promise<{ seconds: number } | null> =>
	request<{ seconds: number }>(`/api/game/rounds/${id}/start`, json({ n }));

/** `key` is null where the clock ran out — a question nobody answered is an
 *  answer, and saying so is what lets the reveal happen anyway. */
export const answer = async (id: number, n: number, key: string | null): Promise<Marked | null> =>
	request<Marked>(`/api/game/rounds/${id}/answer`, json({ n, key }));

export const scores = async (): Promise<{ standing: Standing[]; me: string }> =>
	(await request<{ standing: Standing[]; me: string }>('/api/game/scores')) ?? {
		standing: [],
		me: ''
	};

/* ---- together */

export const party = {
	open: (how: Hardness): Promise<Party | null> =>
		request<Party>('/api/game/parties', json({ hard: HARDNESS[how] })),
	around: async (): Promise<OpenParty[]> =>
		(await request<OpenParty[]>('/api/game/parties')) ?? [],
	state: (id: number): Promise<Party | null> => request<Party>(`/api/game/parties/${id}`),
	join: (id: number): Promise<Party | null> =>
		request<Party>(`/api/game/parties/${id}/join`, { method: 'POST' }),
	ask: (id: number, n: number): Promise<Party | null> =>
		request<Party>(`/api/game/parties/${id}/ask`, json({ n })),
	reveal: (id: number): Promise<Party | null> =>
		request<Party>(`/api/game/parties/${id}/reveal`, { method: 'POST' }),
	answer: (id: number, n: number, key: string | null): Promise<{ answered: boolean } | null> =>
		request<{ answered: boolean }>(`/api/game/parties/${id}/answer`, json({ n, key })),
	close: (id: number): Promise<unknown> =>
		request(`/api/game/parties/${id}`, { method: 'DELETE' })
};
