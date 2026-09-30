/* Putting a phone's pictures away, one at a time.
 *
 * One at a time on purpose. Two uploads at once from a phone on a household
 * connection finish no sooner and make a resume ambiguous, and every picture
 * here is read, hashed, thumbnailed and sealed before a byte of it is sent —
 * work that is done on the one core the browser gives us either way.
 *
 * Nothing here decides what is new. The device asks the server, which answers
 * from the mark: already held, partly held and here is how far, or never seen.
 * That is the only honest answer once the same picture can arrive from a second
 * phone, from a reinstall, or from a person who picked the whole roll again
 * because that is what the iPhone picker makes easy. */

import { TAG, b64, markOf, random, seal, sealPiece, sealedLength } from '$lib/ask/crypto';
import { json } from '$lib/kit';
import { answered, vault } from './vault.svelte';

export type Stage = 'idle' | 'reading' | 'sending' | 'done' | 'failed';

/** How wide a thumbnail is made. Enough for a retina grid cell and small
 * enough that a thousand of them are a few tens of megabytes. */
const THUMB = 480;

class Backup {
	stage = $state<Stage>('idle');
	total = $state(0);
	done = $state(0);
	skipped = $state(0);
	failed = $state(0);
	now = $state('');
	sent = $state(0);
	of = $state(0);
	trouble = $state('');

	#stop = false;

	get running(): boolean {
		return this.stage === 'reading' || this.stage === 'sending';
	}

	halt() {
		this.#stop = true;
	}

	async put(files: File[]) {
		if (this.running) return;
		this.#stop = false;
		this.stage = 'reading';
		this.total = files.length;
		this.done = this.skipped = this.failed = 0;
		this.trouble = '';
		for (const file of files) {
			if (this.#stop) break;
			this.now = file.name;
			try {
				await this.#one(file);
			} catch (why) {
				this.failed++;
				this.trouble = why instanceof Error ? why.message : String(why);
			}
		}
		this.now = '';
		this.stage = this.failed ? 'failed' : 'done';
		await vault.read();
	}

	async #one(file: File): Promise<void> {
		const chunk = vault.chunk;
		const mark = await markOf(vault.mark, file, chunk);
		const base = random(8);
		const contentRaw = random(32);
		const told = {
			name: file.name,
			taken: await takenFrom(file),
			bytes: file.size,
			type: file.type,
			base: b64(base),
			...(await shapeOf(file))
		};

		const said = await answered<{
			id: string;
			known: boolean;
			at: number;
			bytes: number;
			chunk: number;
			keyed: string;
			meta: string;
		}>(
			'/api/photos/vault',
			json({
				mark: b64(mark),
				bytes: sealedLength(file.size, chunk),
				chunk,
				keyed: b64(await seal(vault.key, contentRaw)),
				meta: b64(await seal(vault.key, new TextEncoder().encode(JSON.stringify(told))))
			})
		);

		if (said.known && said.at >= said.bytes) {
			this.skipped++;
			return;
		}
		// A resumed row must keep its first attempt's key and nonce base. A new
		// browser process has fresh random values that cannot open prior pieces.
		const saved = said.known ? await vault.contentKey(said) : contentRaw;
		const savedTold = said.known ? await vault.openMeta(said.meta) : told;
		const content = await crypto.subtle.importKey('raw', saved as BufferSource, 'AES-GCM', false, [
			'encrypt'
		]);
		const savedBase = Uint8Array.from(atob(savedTold.base), (character) => character.charCodeAt(0));

		this.stage = 'sending';
		this.of = said.bytes;
		this.sent = said.at;

		// where to carry on from, in pieces rather than bytes: a piece is sealed
		// as a whole and cannot be resumed halfway into one
		const per = said.chunk + TAG;
		let n = Math.floor(said.at / per);
		let at = n * per;
		if (at !== said.at) {
			// the server holds part of a piece, which can only mean a write that
			// was cut off mid-flight. Nothing can be done with half a sealed
			// piece, so this file starts again.
			await answered(`/api/photos/vault/${said.id}`, { method: 'DELETE' });
			return this.#one(file);
		}

		while (n * said.chunk < file.size) {
			if (this.#stop) return;
			const plain = new Uint8Array(
				await file.slice(n * said.chunk, (n + 1) * said.chunk).arrayBuffer()
			);
			const piece = await sealPiece(content, savedBase, n, plain);
			at = (
				await answered<{ at: number }>(`/api/photos/vault/${said.id}?at=${at}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/octet-stream' },
					body: piece as BodyInit
				})
			).at;
			this.sent = at;
			n++;
		}

		const thumb = await thumbnailOf(file);
		if (thumb) {
			await answered(`/api/photos/vault/${said.id}/thumb`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/octet-stream' },
				body: (await seal(vault.key, thumb)) as BodyInit
			});
		}
		this.done++;
	}
}

/** When the picture was taken, as well as the browser can say.
 *
 * A file picked on a phone keeps its modification time, which for a camera roll
 * is the moment it was shot; a file that has been through a share sheet or a
 * chat app may not. The real answer is in the EXIF and reading it here would
 * mean parsing every format a phone can produce — so the date is taken from the
 * file, said to be from the file, and the day someone needs better than that,
 * the picture is already in the vault to read it from. */
async function takenFrom(file: File): Promise<string> {
	const when = file.lastModified ? new Date(file.lastModified) : new Date();
	return when.toISOString();
}

async function shapeOf(file: File): Promise<{ w?: number; h?: number }> {
	if (!file.type.startsWith('image/')) return {};
	try {
		const bitmap = await createImageBitmap(file);
		const shape = { w: bitmap.width, h: bitmap.height };
		bitmap.close();
		return shape;
	} catch {
		return {};
	}
}

/** A small picture to draw a grid from, made here because the server has
 * nothing to make one from. A video gives up its first quiet frame. */
async function thumbnailOf(file: File): Promise<Uint8Array | null> {
	try {
		const source = file.type.startsWith('video/') ? await firstFrame(file) : await createImageBitmap(file);
		if (!source) return null;
		const scale = THUMB / Math.max(source.width, source.height);
		const w = Math.max(1, Math.round(source.width * Math.min(1, scale)));
		const h = Math.max(1, Math.round(source.height * Math.min(1, scale)));
		const canvas = document.createElement('canvas');
		canvas.width = w;
		canvas.height = h;
		canvas.getContext('2d')?.drawImage(source as CanvasImageSource, 0, 0, w, h);
		const blob = await new Promise<Blob | null>((keep) =>
			canvas.toBlob(keep, 'image/jpeg', 0.78)
		);
		if (source instanceof HTMLVideoElement) URL.revokeObjectURL(source.src);
		else source.close();
		return blob ? new Uint8Array(await blob.arrayBuffer()) : null;
	} catch {
		return null;
	}
}

function firstFrame(file: File): Promise<HTMLVideoElement | null> {
	return new Promise((keep) => {
		const video = document.createElement('video');
		video.preload = 'metadata';
		video.muted = true;
		video.src = URL.createObjectURL(file);
		// the object URL is let go by whoever drew the frame, not here: revoking
		// it at this point leaves the element with nothing to draw from
		const give = (what: HTMLVideoElement | null) => {
			if (!what) URL.revokeObjectURL(video.src);
			keep(what);
		};
		video.onloadeddata = () => {
			// a whole second in, because the first frame of a phone video is
			// very often the lens still opening
			video.currentTime = Math.min(1, (video.duration || 1) / 2);
		};
		video.onseeked = () => give(video);
		video.onerror = () => give(null);
		setTimeout(() => give(null), 8000);
	});
}

export const backup = new Backup();
