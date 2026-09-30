// Where the other OPUS modules answer, for the shell's module switcher: this
// build's own addresses, handed to the package that knows the modules.

import { moduleName, modulesFor } from '$lib/opus';

export const MODULE = moduleName('player');

export const MODULES = modulesFor('player', {
	downloads: import.meta.env.VITE_OPUS_DOWNLOADS_URL,
	library: import.meta.env.VITE_OPUS_LIBRARY_URL
});
