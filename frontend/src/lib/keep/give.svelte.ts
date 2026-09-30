/** Photographs handed straight to the household.
 *
 * The vault's sibling and deliberately not its dependant. Keeping is private
 * and giving is not, and somebody who wants only the second should not have to
 * open a vault to reach it. Nothing here is sealed: what is given is meant to
 * be seen, and the library decides everything about what arrives.
 *
 * The file goes as the body of one request rather than in pieces. A gift is a
 * handful of pictures chosen on purpose, not a roll walked whole, and the
 * resumable machinery the vault needs would be a second protocol to keep
 * honest for no one's benefit. */
/** What the phone's share sheet left for us, taken back out and cleared.
 *
 * Cleared as it is read: these are the one copy of somebody's intent, and a
 * second visit to the photographs must not offer last week's again. */
import { request } from '$lib/kit';

export async function shared(): Promise<File[]> {
	if (!('caches' in globalThis)) return [];
	const held = await caches.open('shared-photographs');
	const files: File[] = [];
	for (const key of await held.keys()) {
		const said = await held.match(key);
		await held.delete(key);
		if (!said) continue;
		const name = decodeURIComponent(said.headers.get('x-shared-name') ?? 'photograph');
		files.push(new File([await said.blob()], name, { type: said.headers.get('content-type') ?? '' }));
	}
	return files;
}

class Give {
	running = $state(false);
	total = $state(0);
	sent = $state(0);
	known = $state(0);
	failed = $state(0);
	now = $state('');
	trouble = $state('');

	async put(files: File[]) {
		this.running = true;
		this.total = files.length;
		this.sent = this.known = this.failed = 0;
		this.trouble = '';
		for (const file of files) {
			this.now = file.name;
			const said = await request<{ known: boolean }>(
				`/api/photos/offer?name=${encodeURIComponent(file.name)}`,
				{ method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file },
				{ failed: (detail) => (this.trouble = `${file.name}: ${detail}`) }
			);
			if (!said) this.failed++;
			// already here is the ordinary answer, not a failure: the same
			// photograph reaches two phones through a chat and both offer it
			else if (said.known) this.known++;
			else this.sent++;
		}
		this.now = '';
		this.running = false;
	}
}

export const give = new Give();
