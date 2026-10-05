import { t } from '$lib/i18n';

const PIECE = 128 * 1024;

export async function saveBlob(blob: Blob, name: string): Promise<void> {
	const box = window.opusTv;
	if (!box) {
		const url = URL.createObjectURL(blob);
		try {
			const link = document.createElement('a');
			link.href = url;
			link.download = name;
			link.click();
		} finally {
			setTimeout(() => URL.revokeObjectURL(url), 1000);
		}
		return;
	}
	if (![box.saveFile, box.fileState, box.writeFile, box.finishFile, box.cancelFile]
		.every((method) => typeof method === 'function')) throw new Error(t('vault.saveUpdate'));
	const id = box.saveFile(name, blob.type || 'application/octet-stream', blob.size);
	if (!id) throw new Error(t('vault.saveFailed'));
	const state = () => JSON.parse(box.fileState(id)) as { state: string; detail: string };
	const failed = () => new Error(state().detail || t('vault.saveFailed'));
	try {
		const deadline = Date.now() + 10 * 60 * 1000;
		let status = state();
		while (status.state === 'waiting') {
			if (Date.now() >= deadline) throw new Error(t('vault.saveTimeout'));
			await new Promise((resolve) => setTimeout(resolve, 100));
			status = state();
		}
		if (status.state === 'cancelled') return;
		if (status.state !== 'ready') throw failed();
		for (let at = 0; at < blob.size; at += PIECE) {
			const bytes = new Uint8Array(await blob.slice(at, at + PIECE).arrayBuffer());
			let raw = '';
			for (let n = 0; n < bytes.length; n += 16384) raw += String.fromCharCode(...bytes.subarray(n, n + 16384));
			if (box.writeFile(id, at, btoa(raw)) !== at + bytes.length) throw failed();
			await new Promise((resolve) => setTimeout(resolve, 0));
		}
		if (!box.finishFile(id)) throw failed();
	} finally {
		box.cancelFile(id);
	}
}
