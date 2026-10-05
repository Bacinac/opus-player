import { afterEach, describe, expect, test, vi } from 'vitest';
import { fromBytes, markKey, openPiece, unb64, unseal } from '$lib/ask/crypto';
import { backup } from './backup.svelte';
import { vault } from './vault.svelte';

type Reservation = {
	id: string;
	known: boolean;
	at: number;
	bytes: number;
	chunk: number;
	keyed: string;
	meta: string;
	thumb: boolean;
};

const reply = (body: unknown) =>
	new Response(JSON.stringify(body), {
		headers: { 'Content-Type': 'application/json' }
	});

function bodyBytes(body: BodyInit | null | undefined): Uint8Array {
	if (body instanceof Uint8Array) return body;
	throw new Error('the backup client must send ciphertext as bytes');
}

describe('vault backup transport', () => {
	const originalChunk = vault.chunk;

	afterEach(() => {
		vault.chunk = originalChunk;
		Reflect.deleteProperty(vault, 'key');
		Reflect.deleteProperty(vault, 'mark');
		vi.restoreAllMocks();
		vi.unstubAllGlobals();
	});

	test('a failed thumbnail is retried without sending the completed original again', async () => {
		const raw = crypto.getRandomValues(new Uint8Array(32));
		const [key, mark] = await Promise.all([fromBytes(raw), markKey(raw)]);
		Object.defineProperties(vault, {
			key: { configurable: true, get: () => key }, mark: { configurable: true, get: () => mark }
		});
		vi.spyOn(vault, 'read').mockResolvedValue();
		vi.spyOn(console, 'error').mockImplementation(() => {});
		vi.stubGlobal('createImageBitmap', async () => ({ width: 10, height: 10, close() {} }));
		vi.stubGlobal('HTMLVideoElement', class {});
		vi.stubGlobal('document', { createElement: () => ({ width: 0, height: 0,
			getContext: () => ({ drawImage() {} }), toBlob: (done: (value: Blob) => void) => done(new Blob(['thumbnail']))
		}) });
		const file = Object.assign(new Blob(['original'], { type: 'image/png' }),
			{ name: 'photo.png', lastModified: Date.UTC(2026, 8, 18) }) as File;
		let reservation: Reservation | null = null;
		let at = 0, originals = 0, thumbnails = 0;
		let held: Uint8Array = new Uint8Array();
		let thumb = false;
		vi.stubGlobal('fetch', async (input: RequestInfo | URL, init: RequestInit = {}) => {
			const url = String(input);
			if (url === '/api/photos/vault') {
				const announced = JSON.parse(String(init.body));
				const known = reservation !== null;
				reservation ??= { ...announced, id: 'photo', known: false, at: 0, thumb: false };
				return reply({ ...reservation, known, at, thumb });
			}
			if (url.startsWith('/api/photos/vault/photo?at=')) {
				originals++;
				held = bodyBytes(init.body);
				at = held.length;
				return reply({ at });
			}
			if (url === '/api/photos/vault/photo/thumb') {
				if (++thumbnails === 1) return new Response(JSON.stringify({ detail: 'thumbnail unavailable' }),
					{ status: 503, headers: { 'Content-Type': 'application/json' } });
				expect(new TextDecoder().decode(await unseal(key, bodyBytes(init.body)))).toBe('thumbnail');
				thumb = true;
				return reply({ thumb });
			}
			throw new Error(`unexpected request: ${url}`);
		});
		await backup.put([file]);
		expect(backup.failed).toBe(1);
		const original = held.slice();
		await backup.put([file]);
		expect(backup.failed).toBe(0);
		expect(backup.skipped).toBe(1);
		expect(originals).toBe(1);
		expect(thumbnails).toBe(2);
		expect(held).toEqual(original);
		await backup.put([file]);
		expect(originals).toBe(1);
		expect(thumbnails).toBe(2);
	});

	test('resumes an interrupted upload with the first reservation encryption material', async () => {
		const vaultRaw = crypto.getRandomValues(new Uint8Array(32));
		const [vaultKey, mark] = await Promise.all([fromBytes(vaultRaw), markKey(vaultRaw)]);
		Object.defineProperties(vault, {
			key: { configurable: true, get: () => vaultKey },
			mark: { configurable: true, get: () => mark }
		});
		vault.chunk = 16;
		vi.spyOn(console, 'error').mockImplementation(() => {});
		vi.spyOn(vault, 'read').mockResolvedValue();

		const plain = crypto.getRandomValues(new Uint8Array(41));
		const file = Object.assign(new Blob([plain], { type: 'application/octet-stream' }), {
			name: 'interrupted.bin',
			lastModified: Date.UTC(2026, 8, 18)
		}) as File;
		let reservation: Reservation | null = null;
		const reservations: Array<Record<string, unknown>> = [];
		let held = new Uint8Array();
		let interrupted = false;

		vi.stubGlobal('fetch', async (input: RequestInfo | URL, init: RequestInit = {}) => {
			const url = String(input);
			if (url === '/api/photos/vault' && init.method === 'POST') {
				const announced = JSON.parse(String(init.body)) as Record<string, unknown>;
				reservations.push(announced);
				if (!reservation) {
					reservation = {
						id: 'first-reservation', known: false, at: 0,
						bytes: Number(announced.bytes), chunk: Number(announced.chunk),
						keyed: String(announced.keyed), meta: String(announced.meta), thumb: false
					};
					return reply(reservation);
				}
				// The Library returns the original row even though this retry announced
				// fresh random keys and a fresh nonce base.
				return reply({ ...reservation, known: true, at: held.length });
			}
			if (url.startsWith('/api/photos/vault/first-reservation?at=') && init.method === 'PUT') {
				const at = Number(new URL(`https://opus.invalid${url}`).searchParams.get('at'));
				if (!interrupted && held.length > 0) {
					interrupted = true;
					throw new TypeError('connection interrupted');
				}
				expect(at).toBe(held.length);
				const piece = bodyBytes(init.body);
				held = new Uint8Array([...held, ...piece]);
				return reply({ at: held.length });
			}
			throw new Error(`unexpected request: ${init.method ?? 'GET'} ${url}`);
		});

		await backup.put([file]);
		expect(backup.failed).toBe(1);
		expect(held.length).toBe(32); // first 16-byte plaintext piece plus its tag

		await backup.put([file]);
		expect(backup.failed).toBe(0);
		expect(backup.done).toBe(1);
		expect(reservations).toHaveLength(2);
		expect(reservations[1].keyed).not.toBe(reservation!.keyed);
		expect(reservations[1].meta).not.toBe(reservation!.meta);

		const told = JSON.parse(
			new TextDecoder().decode(await unseal(vaultKey, unb64(reservation!.meta)))
		) as { base: string };
		const content = await fromBytes(await unseal(vaultKey, unb64(reservation!.keyed)));
		const opened: Uint8Array[] = [];
		let at = 0;
		for (let piece = 0; at < held.length; piece++) {
			const size = Math.min(reservation!.chunk + 16, held.length - at);
			opened.push(await openPiece(content, unb64(told.base), piece, held.subarray(at, at + size)));
			at += size;
		}
		expect(new Uint8Array(opened.flatMap((piece) => [...piece]))).toEqual(plain);
	});
});
