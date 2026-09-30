import { t } from '$lib/i18n';
import { toasts } from '$lib/kit';

type Box = NonNullable<Window['opusTv']>;

/** Something asked of the box this page runs in, where there is one. The
 *  wrapper refuses what it will not do by throwing, and a refusal is said —
 *  by `failed` where the caller shows it itself, as a toast otherwise. */
export function onBox<T>(asking: (box: Box) => T, failed?: (detail: string) => void): T | undefined {
	const box = typeof window === 'undefined' ? undefined : window.opusTv;
	if (!box) return undefined;
	try {
		return asking(box);
	} catch (why) {
		const detail = t('tv.refused', { detail: why instanceof Error ? why.message : String(why) });
		if (failed) failed(detail);
		else toasts.error(detail);
		return undefined;
	}
}
