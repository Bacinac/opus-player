/* The vault, as the app holds it: locked or open, and what is in it.
 *
 * The key lives here and nowhere else. It is kept on the device only if the
 * person says so — and a phone that is meant to back up on its own has to say
 * so, because a key that is gone when the app is closed is a backup that only
 * happens while somebody is watching it. That is a real trade and the screen
 * makes it, not this file.
 *
 * The index is fetched once and kept, because it has to be: the server cannot
 * sort a vault by date, cannot search it, cannot tell you what is in it. Every
 * one of those questions is answered here, over blobs decrypted on this device. */

import {
	CHUNK,
	ROUNDS,
	TAG,
	b64,
	fromBytes,
	fromPassword,
	markKey,
	openPiece,
	seal,
	sealedLength,
	unb64,
	unseal
} from '$lib/ask/crypto';
import { t } from '$lib/i18n';
import { TRANSFER_MS, bytes, json, request } from '$lib/kit';

/** What was asked, or an error saying why not: every step of the vault and of
 * the backup into it is taken inside a guard that shows the person what went
 * wrong. */
export async function answered<T>(url: string, init: RequestInit = {}): Promise<T> {
	let why = '';
	const said = await request<T>(url, init, { failed: (detail) => (why = detail) });
	if (said === null) throw new Error(why);
	return said;
}

async function sealed(url: string, deadlineMs?: number): Promise<Uint8Array> {
	let why = '';
	const said = await bytes(url, { deadlineMs }, { failed: (detail) => (why = detail) });
	if (said === null) throw new Error(why);
	return new Uint8Array(said);
}

/** Kept as CryptoKeys that cannot be exported: a script in this page can use
 * one while it runs and can never carry it anywhere. The recovery wrap tells a
 * key for this vault from one for a vault made again since. */
type Kept = { vault: string; key: CryptoKey; mark: CryptoKey };

const DATABASE = 'opus-vault';
const SHELF = 'keys';

function database(): Promise<IDBDatabase> {
	return new Promise((opened, failed) => {
		const asking = indexedDB.open(DATABASE, 1);
		asking.onupgradeneeded = () => asking.result.createObjectStore(SHELF);
		asking.onsuccess = () => opened(asking.result);
		asking.onerror = () => failed(asking.error);
	});
}

async function onShelf<T>(
	mode: IDBTransactionMode,
	work: (shelf: IDBObjectStore) => IDBRequest<T>
): Promise<T> {
	const db = await database();
	try {
		return await new Promise<T>((done, failed) => {
			const doing = db.transaction(SHELF, mode);
			const asked = work(doing.objectStore(SHELF));
			doing.oncomplete = () => done(asked.result);
			doing.onerror = () => failed(doing.error ?? asked.error);
			doing.onabort = () => failed(doing.error ?? asked.error);
		});
	} finally {
		db.close();
	}
}

const LEGACY = 'opus.vault.key';

function dropLegacy() {
	let names: string[];
	try {
		names = Object.keys(localStorage);
	} catch {
		return;
	}
	for (const name of names) if (name.startsWith(LEGACY)) localStorage.removeItem(name);
}

/** Everybody's, not only the last person's: with nobody signed in there is
 * nobody whose vault a key on this device should open. */
export async function forgetKeys() {
	vault.lock();
	vault.kept = false;
	dropLegacy();
	await onShelf('readwrite', (shelf) => shelf.clear());
}

export type Held = {
	id: string;
	mark: string;
	bytes: number;
	at: number;
	chunk: number;
	keyed: string;
	meta: string;
	thumb: boolean;
	photo_id: number | null;
};

/** What a picture says about itself, once opened. Everything here would have
 * been a column on a table if the server were allowed to read it. */
export type Told = {
	name: string;
	taken: string;
	bytes: number;
	type: string;
	w?: number;
	h?: number;
	base: string;
	gps?: [number, number];
};

export type Item = Held & { told: Told };

class Vault {
	enrolled = $state<boolean | null>(null);
	open = $state(false);
	/** whether this device holds the key for the vault as it stands: with one,
	 * locking is a door that opens again from the same side */
	kept = $state(false);
	chunk = $state(CHUNK);
	items = $state<Item[]>([]);
	unreadable = $state(0);
	reading = $state(false);

	#key: CryptoKey | null = null;
	#mark: CryptoKey | null = null;
	#person = '';
	#vault = '';

	of(person: string) {
		dropLegacy();
		if (person === this.#person) return;
		this.lock();
		this.#person = person;
		this.#vault = '';
		this.enrolled = null;
		this.kept = false;
	}

	get key(): CryptoKey {
		if (!this.#key) throw new Error(t('vault.locked'));
		return this.#key;
	}

	get mark(): CryptoKey {
		if (!this.#mark) throw new Error(t('vault.locked'));
		return this.#mark;
	}

	/** Open it with the key left on this device, if one was left for this
	 * vault. Asked before the screen decides whether to show a password box. */
	async resume(): Promise<boolean> {
		const person = this.#person;
		const held = await onShelf<Kept | undefined>('readonly', (shelf) => shelf.get(person));
		if (held && this.#vault && held.vault === this.#vault) {
			this.#key = held.key;
			this.#mark = held.mark;
			this.open = true;
			this.kept = true;
			return true;
		}
		if (held) await this.#drop();
		this.kept = false;
		return false;
	}

	async #hold(raw: Uint8Array, keep: boolean) {
		const [key, mark] = await Promise.all([fromBytes(raw), markKey(raw)]);
		this.#key = key;
		this.#mark = mark;
		this.open = true;
		const person = this.#person;
		if (keep) {
			const kept: Kept = { vault: this.#vault, key, mark };
			await onShelf('readwrite', (shelf) => shelf.put(kept, person));
			this.kept = true;
		} else if (this.kept) {
			await this.#drop();
		}
	}

	async #drop() {
		const person = this.#person;
		this.kept = false;
		await onShelf('readwrite', (shelf) => shelf.delete(person));
	}

	/** Shut it. The key stays where it was left — on this device if it was kept
	 * there, nowhere if it was not — so somebody who told this phone to remember
	 * is not made to type the password again for having closed the lid. */
	lock() {
		this.#key = null;
		this.#mark = null;
		this.open = false;
		this.items = [];
		this.unreadable = 0;
	}

	/** And the other thing, which is not the same thing: the key leaves this
	 * device. After this the password or the recovery code is the only way in,
	 * which is the point of it. */
	async forget() {
		this.lock();
		await this.#drop();
	}

	async ask(): Promise<Record<string, unknown>> {
		const said = await answered<Record<string, unknown> & { enrolled?: boolean; chunk?: number }>(
			'/api/photos/vault/keys'
		);
		this.enrolled = !!said.enrolled;
		this.#vault = String(said.recovery ?? '');
		if (said.chunk) this.chunk = said.chunk;
		return said;
	}

	/** Make a vault: one random key, wrapped twice under two things the person
	 * knows. The key itself never leaves this function unwrapped. */
	async enrol(password: string, code: string, keep: boolean) {
		const raw = crypto.getRandomValues(new Uint8Array(32));
		const salt = crypto.getRandomValues(new Uint8Array(16));
		const recoverySalt = crypto.getRandomValues(new Uint8Array(16));
		const [byPassword, byCode] = await Promise.all([
			fromPassword(password, salt),
			fromPassword(code, recoverySalt)
		]);
		const recovery = b64(await seal(byCode, raw));
		await answered(
			'/api/photos/vault/keys',
			json({
				salt: b64(salt),
				rounds: ROUNDS,
				wrapped: b64(await seal(byPassword, raw)),
				recovery_salt: b64(recoverySalt),
				recovery
			})
		);
		this.enrolled = true;
		this.#vault = recovery;
		await this.#hold(raw, keep);
	}

	/** Open it with either of the two things that can. The recovery code also
	 * re-wraps under the password given alongside it, so a person who has been
	 * locked out by a password change is not locked out again tomorrow. */
	async unlock(secret: string, how: 'password' | 'code', keep: boolean, andSetTo?: string) {
		const said = await this.ask();
		const salt = unb64(String(how === 'password' ? said.salt : said.recovery_salt));
		const blob = unb64(String(how === 'password' ? said.wrapped : said.recovery));
		const key = await fromPassword(secret, salt, Number(said.rounds));
		const raw = await unseal(key, blob);
		await this.#hold(raw, keep);
		if (how === 'code' && andSetTo) await this.#rewrap(raw, andSetTo);
	}

	/** The same key under a new password, while its bytes are still in hand:
	 * the key kept on a device cannot be read back out to wrap again. */
	async #rewrap(raw: Uint8Array, password: string) {
		const salt = crypto.getRandomValues(new Uint8Array(16));
		await answered(
			'/api/photos/vault/keys',
			json(
				{
					salt: b64(salt),
					rounds: ROUNDS,
					wrapped: b64(await seal(await fromPassword(password, salt), raw))
				},
				'PATCH'
			)
		);
	}

	/** Everything in it, opened. One page at a time from the server; the sort is
	 * here, because a date is something only this device can read. */
	async read() {
		this.reading = true;
		try {
			const out: Item[] = [];
			let unreadable = 0;
			let after = '';
			for (;;) {
				const page = await answered<{ files: Held[]; more: boolean }>(
					`/api/photos/vault?after=${encodeURIComponent(after)}`
				);
				for (const held of page.files) {
					try {
						const told = JSON.parse(
							new TextDecoder().decode(await unseal(this.key, unb64(held.meta)))
						) as Told;
						out.push({ ...held, told });
					} catch {
						unreadable += 1;
					}
				}
				if (!page.more) break;
				after = page.files[page.files.length - 1].id;
			}
			out.sort((a, b) => (a.told.taken < b.told.taken ? 1 : -1));
			this.items = out;
			this.unreadable = unreadable;
		} finally {
			this.reading = false;
		}
	}

	/** A thumbnail as this device can show it. */
	async picture(item: Item): Promise<string> {
		const blob = await unseal(this.key, await sealed(`/api/photos/vault/${item.id}/thumb`));
		return URL.createObjectURL(new Blob([blob as BlobPart], { type: 'image/jpeg' }));
	}

	/** The whole picture, opened piece by piece exactly as it was sealed. The
	 * length is checked against the size sealed into the metadata first: every
	 * piece carries its own tag and position, so a file cut at a piece boundary
	 * would otherwise open cleanly and simply be shorter. */
	async whole(item: Item): Promise<Blob> {
		const whole = await sealed(`/api/photos/vault/${item.id}/bytes`, TRANSFER_MS);
		if (whole.length !== sealedLength(item.told.bytes, item.chunk)) throw new Error(t('vault.notWhole'));
		const base = unb64(item.told.base);
		const pieces: Uint8Array[] = [];
		const content = await fromBytes(await this.contentKey(item));
		let at = 0;
		for (let n = 0; at < whole.length; n++) {
			const take = Math.min(item.chunk + TAG, whole.length - at);
			pieces.push(await openPiece(content, base, n, whole.subarray(at, at + take)));
			at += take;
		}
		return new Blob(pieces as BlobPart[], { type: item.told.type || 'application/octet-stream' });
	}

	/** The key to one picture, unwrapped. Handed to the server only when its
	 * owner offers that picture to the household — it opens that photograph and
	 * no other, and the vault key it was wrapped under never leaves here. */
	async contentKey(item: Pick<Held, 'keyed'>): Promise<Uint8Array> {
		return unseal(this.key, unb64(item.keyed));
	}

	/** Upload metadata is needed again when a reservation is resumed. */
	async openMeta(meta: string): Promise<Told> {
		return JSON.parse(new TextDecoder().decode(await unseal(this.key, unb64(meta)))) as Told;
	}

	/** What the vault costs, in the only terms the server can count. */
	async weight(): Promise<{ files: number; complete: number; bytes: number }> {
		return answered('/api/photos/vault/stat');
	}
}

export const vault = new Vault();
