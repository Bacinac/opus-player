/// <reference types="@sveltejs/kit" />
/// <reference lib="esnext" />
/// <reference lib="webworker" />

const sw = self as unknown as ServiceWorkerGlobalScope;

/** Where photographs wait between the share sheet and the page that sends them.
 *
 * The gallery posts them here, and a post is a navigation: it arrives with no
 * origin the app's own defences would accept, and it cannot carry a progress
 * bar either. So it never reaches the network. This holds what was shared, hands
 * the person back to the photographs, and the page sends them the same way the
 * button does — one mechanism, two doors into it. */
const HELD = 'shared-photographs';

sw.addEventListener('install', () => sw.skipWaiting());
sw.addEventListener('activate', (event) => event.waitUntil(sw.clients.claim()));

// Nothing is cached here on purpose. A worker that also served the app would
// decide when a television sees a new build, and that decision already belongs
// to `version.pollInterval`.
sw.addEventListener('fetch', (event) => {
	const url = new URL(event.request.url);
	if (event.request.method !== 'POST' || url.pathname !== '/share') return;

	event.respondWith(
		(async () => {
			const given = await event.request.formData();
			const files = given.getAll('given').filter((one): one is File => one instanceof File);
			// what an earlier share left unsent is not part of this one
			await caches.delete(HELD);
			const held = await caches.open(HELD);
			await Promise.all(
				files.map((file, n) =>
					held.put(
						`/shared/${n}`,
						new Response(file, {
							headers: {
								'content-type': file.type || 'application/octet-stream',
								// the name does not survive a Response on its own
								'x-shared-name': encodeURIComponent(file.name)
							}
						})
					)
				)
			);
			return Response.redirect(`/photos?shared=${files.length}`, 303);
		})()
	);
});
