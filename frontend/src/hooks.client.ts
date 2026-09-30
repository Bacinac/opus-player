import type { HandleClientError } from '@sveltejs/kit';
import { version } from '$app/environment';

// A television has no console anyone can read, so a page that breaks there is
// said in the backend's log, beside the wrapper's own crashes.
const said = new Set<string>();

function report(error: unknown, where: string, message = '') {
	const stack = (
		error instanceof Error ? error.stack || `${error.name}: ${error.message}` : String(error ?? message)
	).slice(0, 16000);
	// a timer that breaks every half second would otherwise fill the log
	if (said.has(stack)) return;
	said.add(stack);
	void fetch('/api/app/crash-report', {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({
			app: 'web',
			version,
			thread: where.slice(0, 200),
			stack: stack || 'unknown',
			occurred_at_ms: Date.now(),
			device: navigator.userAgent.slice(0, 200)
		})
	}).catch(() => {});
}

export const handleError: HandleClientError = ({ error, event, status, message }) => {
	if (status === 404) return;
	report(error, event.url.pathname, message);
};

// what breaks in an effect, a timer or an order from the house never passes
// through a navigation, and a block whose effect threw renders nothing again
window.addEventListener('error', (event) => report(event.error, location.pathname, event.message));
window.addEventListener('unhandledrejection', (event) => report(event.reason, location.pathname));
