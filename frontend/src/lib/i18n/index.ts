// The module's catalogues, registered into the shared runtime.

import { hr } from './hr';
import { en } from './en';
import { registerModule, type Word } from '$lib/opus';

// this module's own words, widened with the ones the shared package says on
// its behalf — both halves stay checked, neither is written twice
export type MessageKey = keyof typeof hr | Word;

export const t = registerModule({ hr, en });
export {
	i18n,
	duration,
	formatNumber,
	formatDateTime,
	formatTime,
	formatDate,
	formatBytes,
	formatRuntime,
	plural
} from '$lib/kit';
export type { Locale } from '$lib/kit';
