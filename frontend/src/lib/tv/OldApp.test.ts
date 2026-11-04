// @vitest-environment happy-dom
import { afterEach, expect, test, vi } from 'vitest';
import { flushSync, mount, unmount } from 'svelte';
import OldApp from './OldApp.svelte';

let shown: ReturnType<typeof mount> | null = null;
afterEach(async () => {
	if (shown) await unmount(shown);
	shown = null;
	vi.unstubAllGlobals();
	delete (window as { opusTv?: unknown }).opusTv;
	document.body.innerHTML = '';
});

const shelf = vi.fn(async () =>
	new Response(JSON.stringify({ versionCode: 10000065, versionName: 'v1.0.65', bytes: 1 }), {
		headers: { 'Content-Type': 'application/json' }
	})
);

async function opened(box: object): Promise<string> {
	shelf.mockClear();
	vi.stubGlobal('fetch', shelf);
	(window as { opusTv?: unknown }).opusTv = box;
	shown = mount(OldApp, { target: document.body });
	await new Promise((settle) => setTimeout(settle, 0));
	flushSync();
	return document.body.textContent ?? '';
}

test('a box on an app that cannot update itself is told how, once the shelf has a newer one', async () => {
	expect(await opened({ version: () => 10000040 })).toContain('v1.0.65');
	expect(document.querySelectorAll('.old-app li')).toHaveLength(3);
});

test('a box whose app updates itself, or is already current, is not told anything', async () => {
	expect(await opened({ version: () => 10000064, update: () => {} })).not.toContain('v1.0.65');
	expect(shelf).not.toHaveBeenCalled();
	if (shown) await unmount(shown);
	shown = null;
	expect(await opened({ version: () => 10000065 })).not.toContain('v1.0.65');
});
