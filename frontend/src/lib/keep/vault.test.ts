import { afterEach, describe, expect, test, vi } from 'vitest';
import { b64, fromBytes, seal, sealPiece } from '$lib/ask/crypto';
import { vault, type Item } from './vault.svelte';

describe('opening a vault file', () => {
	afterEach(() => {
		Reflect.deleteProperty(vault, 'key');
		vi.unstubAllGlobals();
	});

	async function sealedFile(chunk: number, plain: Uint8Array) {
		const vaultKey = await fromBytes(crypto.getRandomValues(new Uint8Array(32)));
		Object.defineProperty(vault, 'key', { configurable: true, get: () => vaultKey });
		const contentRaw = crypto.getRandomValues(new Uint8Array(32));
		const content = await crypto.subtle.importKey('raw', contentRaw, 'AES-GCM', false, ['encrypt']);
		const base = crypto.getRandomValues(new Uint8Array(8));
		const pieces: Uint8Array[] = [];
		for (let n = 0; n * chunk < plain.length; n++)
			pieces.push(await sealPiece(content, base, n, plain.subarray(n * chunk, (n + 1) * chunk)));
		const item = {
			id: 'f1',
			chunk,
			keyed: b64(await seal(vaultKey, contentRaw)),
			told: { name: 'a.bin', taken: '', bytes: plain.length, type: 'application/octet-stream', base: b64(base) }
		} as Item;
		return { item, pieces };
	}

	const serve = (body: Uint8Array) =>
		vi.stubGlobal('fetch', async () => new Response(body as BodyInit, { headers: { 'Content-Type': 'application/octet-stream' } }));

	const joined = (pieces: Uint8Array[]) => new Uint8Array(pieces.flatMap((piece) => [...piece]));

	test('opens a file that is all there', async () => {
		const plain = crypto.getRandomValues(new Uint8Array(40));
		const { item, pieces } = await sealedFile(16, plain);
		serve(joined(pieces));
		const opened = new Uint8Array(await (await vault.whole(item)).arrayBuffer());
		expect(opened).toEqual(plain);
	});

	test('refuses a file cut off at a piece boundary', async () => {
		const plain = crypto.getRandomValues(new Uint8Array(40));
		const { item, pieces } = await sealedFile(16, plain);
		serve(joined(pieces.slice(0, 2)));
		await expect(vault.whole(item)).rejects.toThrow();
	});
});
