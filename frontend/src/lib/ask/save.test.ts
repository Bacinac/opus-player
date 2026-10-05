import { afterEach, expect, test, vi } from 'vitest';
import { saveBlob } from './save';

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

test('native export acknowledges bounded pieces and produces the original bytes', async () => {
	const original = new Uint8Array(128 * 1024 * 2 + 19).map((_, n) => n % 251);
	const pieces: Buffer[] = [];
	let at = 0;
	const box = {
		saveFile: vi.fn(() => 'request'),
		fileState: () => JSON.stringify({ state: 'ready' }),
		writeFile: vi.fn((id: string, offset: number, data: string) => {
			expect(id).toBe('request');
			expect(offset).toBe(at);
			const bytes = Buffer.from(data, 'base64');
			expect(bytes.length).toBeLessThanOrEqual(128 * 1024);
			pieces.push(bytes);
			return at += bytes.length;
		}),
		finishFile: vi.fn(() => true),
		cancelFile: vi.fn()
	};
	vi.stubGlobal('window', { opusTv: box });
	await saveBlob(new Blob([original], { type: 'image/png' }), 'original.png');
	expect(Buffer.concat(pieces)).toEqual(Buffer.from(original));
	expect(box.saveFile).toHaveBeenCalledWith('original.png', 'image/png', original.length);
	expect(box.finishFile).toHaveBeenCalledWith('request');
	expect(box.cancelFile).toHaveBeenCalledWith('request');
});

test('a cancelled document picker writes no bytes', async () => {
	const box = { saveFile: () => 'request', fileState: () => JSON.stringify({ state: 'cancelled' }),
		writeFile: vi.fn(), finishFile: vi.fn(), cancelFile: vi.fn() };
	vi.stubGlobal('window', { opusTv: box });
	await saveBlob(new Blob(['original']), 'original.png');
	expect(box.writeFile).not.toHaveBeenCalled();
	expect(box.finishFile).not.toHaveBeenCalled();
	expect(box.cancelFile).toHaveBeenCalledWith('request');
});

test('a provider write refusal aborts the export and is reported', async () => {
	let failed = false;
	const box = { saveFile: () => 'request',
		fileState: () => JSON.stringify({ state: failed ? 'failed' : 'ready', detail: 'provider unavailable' }),
		writeFile: () => { failed = true; return -1; }, finishFile: vi.fn(), cancelFile: vi.fn() };
	vi.stubGlobal('window', { opusTv: box });
	await expect(saveBlob(new Blob(['original']), 'original.png')).rejects.toThrow('provider unavailable');
	expect(box.finishFile).not.toHaveBeenCalled();
	expect(box.cancelFile).toHaveBeenCalledWith('request');
});

test('a native app without file export reports the required update', async () => {
	vi.stubGlobal('window', { opusTv: {} });
	await expect(saveBlob(new Blob(['original']), 'original.png')).rejects.toThrow();
});
