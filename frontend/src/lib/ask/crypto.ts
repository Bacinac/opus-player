/* The vault's cryptography, and the only place in the app that holds a key.
 *
 * Everything here runs on the device. The server is handed ciphertext and never
 * anything that could open it — not the password, not the key derived from it,
 * not the key that derived. What the server keeps is two wrapped copies of one
 * random key, and it can open neither.
 *
 * AES-GCM and PBKDF2 rather than anything more fashionable because both are in
 * the browser already: a vault whose cryptography needs a megabyte of WebAssembly
 * downloaded before a phone can back anything up is a vault that does not run
 * where it has to run. The cost is that PBKDF2 is weaker per round than Argon2,
 * which is answered by rounds — six hundred thousand, about a second on a phone,
 * and the number travels with the salt so it can be raised later without locking
 * out a device that has not opened in a year.
 *
 * Web Crypto exists only in a secure context. Over plain http `crypto.subtle` is
 * undefined and every call here would fail late and obscurely, so `available()`
 * asks up front and the screen says so plainly instead. */

import { sha256 } from '@noble/hashes/sha2.js';

export const ROUNDS = 600_000;

/** Plaintext bytes sealed as one piece. The server's own chunk size travels
 * with the enrolment answer; this is the fallback if it ever does not. */
export const CHUNK = 4 * 1024 * 1024;

/** AES-GCM appends a 16-byte tag to every piece it seals. */
export const TAG = 16;

export function available(): boolean {
	return typeof crypto !== 'undefined' && !!crypto.subtle;
}

export const b64 = (data: ArrayBuffer | Uint8Array): string => {
	const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
	let out = '';
	// in chunks, because a camera roll's worth of bytes passed to String.
	// fromCharCode as one spread argument overflows the call stack
	for (let i = 0; i < bytes.length; i += 8192)
		out += String.fromCharCode(...bytes.subarray(i, i + 8192));
	return btoa(out);
};

export const unb64 = (text: string): Uint8Array =>
	Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

export const random = (n: number): Uint8Array => crypto.getRandomValues(new Uint8Array(n));

/** The key a password opens the vault with. Never sent anywhere. */
export async function fromPassword(
	password: string,
	salt: Uint8Array,
	rounds = ROUNDS
): Promise<CryptoKey> {
	const material = await crypto.subtle.importKey(
		'raw',
		new TextEncoder().encode(password),
		'PBKDF2',
		false,
		['deriveKey']
	);
	return crypto.subtle.deriveKey(
		{ name: 'PBKDF2', salt: salt as BufferSource, iterations: rounds, hash: 'SHA-256' },
		material,
		{ name: 'AES-GCM', length: 256 },
		false,
		['encrypt', 'decrypt']
	);
}

/** A key made of bytes we already hold — the vault key itself, once unwrapped. */
export const fromBytes = (raw: Uint8Array): Promise<CryptoKey> =>
	crypto.subtle.importKey('raw', raw as BufferSource, 'AES-GCM', false, [
		'encrypt',
		'decrypt'
	]);

/** Seal with a fresh nonce carried in front of the ciphertext. Used for the
 * small things — a key, a metadata blob, a thumbnail — where one piece is the
 * whole thing. */
export async function seal(key: CryptoKey, plain: Uint8Array): Promise<Uint8Array> {
	const nonce = random(12);
	const sealed = new Uint8Array(
		await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce as BufferSource }, key, plain as BufferSource)
	);
	const out = new Uint8Array(nonce.length + sealed.length);
	out.set(nonce);
	out.set(sealed, nonce.length);
	return out;
}

export async function unseal(key: CryptoKey, blob: Uint8Array): Promise<Uint8Array> {
	const nonce = blob.subarray(0, 12);
	return new Uint8Array(
		await crypto.subtle.decrypt(
			{ name: 'AES-GCM', iv: nonce as BufferSource },
			key,
			blob.subarray(12) as BufferSource
		)
	);
}

/* A file is sealed piece by piece, so a phone never holds more than one piece in
 * memory and an interrupted upload resumes at a piece boundary. Every piece of
 * one file shares an eight-byte base and differs in a four-byte counter, which
 * is what keeps a nonce from ever repeating under the same key — the one thing
 * AES-GCM must never do. The base lives in the file's encrypted metadata, so
 * reading a file back needs the vault key even to know where to start. */

const nonceFor = (base: Uint8Array, n: number): Uint8Array => {
	const nonce = new Uint8Array(12);
	nonce.set(base);
	new DataView(nonce.buffer).setUint32(8, n, false);
	return nonce;
};

export const sealPiece = async (
	key: CryptoKey,
	base: Uint8Array,
	n: number,
	plain: Uint8Array
): Promise<Uint8Array> =>
	new Uint8Array(
		await crypto.subtle.encrypt(
			{ name: 'AES-GCM', iv: nonceFor(base, n) as BufferSource },
			key,
			plain as BufferSource
		)
	);

export const openPiece = async (
	key: CryptoKey,
	base: Uint8Array,
	n: number,
	blob: Uint8Array
): Promise<Uint8Array> =>
	new Uint8Array(
		await crypto.subtle.decrypt(
			{ name: 'AES-GCM', iv: nonceFor(base, n) as BufferSource },
			key,
			blob as BufferSource
		)
	);

/** How long a file becomes once sealed: every piece carries a tag. */
export const sealedLength = (bytes: number, chunk = CHUNK): number =>
	bytes + Math.ceil(bytes / chunk) * TAG;

export const markKey = (raw: Uint8Array): Promise<CryptoKey> =>
	crypto.subtle.importKey('raw', raw as BufferSource, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);

/** How the same picture is recognised on a second phone, or after a
 * reinstall, without the server learning what it is. A plain digest would let
 * anyone holding the database test whether a person owns a particular known
 * image; keyed by the vault key, it collides only inside one vault and means
 * nothing outside it.
 *
 * The digest is taken a piece at a time: Web Crypto only digests what it holds
 * whole, and a phone's video is several gigabytes it cannot hold. */
export async function markOf(mark: CryptoKey, file: Blob, piece = CHUNK): Promise<Uint8Array> {
	const digest = sha256.create();
	for (let at = 0; at < file.size; at += piece) {
		digest.update(new Uint8Array(await file.slice(at, at + piece).arrayBuffer()));
	}
	return new Uint8Array(await crypto.subtle.sign('HMAC', mark, digest.digest() as BufferSource));
}

/** The code that opens the vault when the password cannot. Read aloud and
 * written down, so: no padding, no lower case, and none of the four characters
 * people mistake for one another. */
export function recoveryCode(): string {
	const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
	const raw = random(20);
	const letters = Array.from(raw, (b) => alphabet[b % alphabet.length]);
	return (letters.join('').match(/.{1,5}/g) ?? []).join('-');
}
