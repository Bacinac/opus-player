// @vitest-environment happy-dom
import { afterEach, expect, test } from 'vitest';
import { flushSync, mount, unmount } from 'svelte';
import BackDialog from './BackDialog.test.svelte';
import { goBack } from './back.svelte';

let host: ReturnType<typeof mount> | null = null;
afterEach(async () => {
	if (host) await unmount(host);
	host = null;
	document.body.innerHTML = '';
});

function click(label: string) {
	const button = [...document.querySelectorAll('button')].find(b => b.textContent === label);
	expect(button).toBeDefined();
	flushSync(() => button!.click());
}

function open() {
	flushSync(() => { host = mount(BackDialog, { target: document.body }); });
	click('Open dialog');
}

function escape() {
	const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
	flushSync(() => document.activeElement!.dispatchEvent(event));
	expect(event.defaultPrevented).toBe(true);
}

test('Escape closes the dialog before the earlier page navigation listener', () => {
	open();
	escape();
	expect(document.querySelector('[role="dialog"]')).toBeNull();
	expect(document.querySelector('output')?.textContent).toBe('0');
});

test('native Back closes a dialog before navigating the underlying page', () => {
	open();
	flushSync(() => expect(goBack()).toBe(true));
	expect(document.querySelector('[role="dialog"]')).toBeNull();
	expect(document.querySelector('output')?.textContent).toBe('0');
});

test('nested dialogs consume one Escape or native Back per layer', () => {
	open();
	click('Open nested dialog');
	escape();
	expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1);
	expect(document.querySelector('[role="dialog"] h2')?.textContent).toBe('Outer');
	flushSync(() => expect(goBack()).toBe(true));
	expect(document.querySelector('[role="dialog"]')).toBeNull();
	expect(document.querySelector('output')?.textContent).toBe('0');
	flushSync(() => expect(goBack()).toBe(true));
	expect(document.querySelector('output')?.textContent).toBe('1');
});
