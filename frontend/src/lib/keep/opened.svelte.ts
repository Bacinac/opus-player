// The ways into music that stand on what the installation added to the
// Library, asked once somebody is in.

import { request } from '$lib/kit';

class OpenedState {
	music = $state<string[]>([]);
	private asked = false;

	async ask() {
		if (this.asked) return;
		this.asked = true;
		const said = await request<{ music: string[] }>('/api/explore/ways');
		if (said) this.music = said.music;
		else this.asked = false;
	}
}

export const opened = new OpenedState();
