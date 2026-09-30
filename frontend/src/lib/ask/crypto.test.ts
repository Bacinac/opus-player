import { describe, expect, test } from 'vitest';
import { fromBytes, markKey, markOf, openPiece, random, seal, sealPiece, sealedLength, unseal } from './crypto';

describe('markOf', () => {
	test('read a piece at a time, it is the mark the whole file always had', async () => {
		const raw = crypto.getRandomValues(new Uint8Array(32));
		const plain = crypto.getRandomValues(new Uint8Array(1000));
		const hmac = await crypto.subtle.importKey('raw', raw, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
		const whole = new Uint8Array(
			await crypto.subtle.sign('HMAC', hmac, await crypto.subtle.digest('SHA-256', plain))
		);
		const mark = await markKey(raw);
		expect(mark.extractable).toBe(false);
		expect(await markOf(mark, new Blob([plain]), 64)).toEqual(whole);
		expect(await markOf(mark, new Blob([plain]))).toEqual(whole);
	});
});

describe('sealedLength', () => {
	test('every piece carries a tag', () => {
		expect(sealedLength(0, 16)).toBe(0);
		expect(sealedLength(16, 16)).toBe(32);
		expect(sealedLength(17, 16)).toBe(49);
	});
});

describe('vault file recovery', () => {
	test('a wrapped per-file key restores every interrupted-upload piece', async () => {
		const vault = await fromBytes(random(32));
		const contentRaw = random(32);
		const content = await fromBytes(contentRaw);
		const wrappedContent = await seal(vault, contentRaw);
		const base = random(8);
		const plain = crypto.getRandomValues(new Uint8Array(37));
		const chunk = 16;
		const encrypted: Uint8Array[] = [];
		for (let n = 0; n * chunk < plain.length; n++) {
			encrypted.push(await sealPiece(content, base, n, plain.subarray(n * chunk, (n + 1) * chunk)));
		}

		// A later browser process has only the wrapped content key, nonce base
		// and ciphertext returned by the server's original reservation.
		const restoredKey = await fromBytes(await unseal(vault, wrappedContent));
		const restored = new Uint8Array(
			(await Promise.all(encrypted.map((piece, n) => openPiece(restoredKey, base, n, piece)))).flatMap(
				(piece) => [...piece]
			)
		);
		expect(restored).toEqual(plain);
		await expect(openPiece(vault, base, 0, encrypted[0])).rejects.toThrow();
	});
});
