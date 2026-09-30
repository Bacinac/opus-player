<script lang="ts">
	import Grid from '$lib/parts/Grid.svelte';
	import { queue } from '$lib/keep/queue.svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { focusContent } from '$lib/tv/spatial.svelte';
	import { request } from '$lib/kit';
	import type { Card } from '$lib/keep/types';

	// the stations, which are the one thing here with no file behind them. They
	// are shown the way records are, because that is what they are to a person
	// standing in the room: something to put on.
	let stations = $state<Card[]>([]);

	$effect(() => {
		void request<{ stations: Card[] }>('/api/radio/stations').then((got) => {
			stations = got?.stations ?? [];
			if (surface.isTv) setTimeout(focusContent, 0);
		});
	});

	/** A station is a queue of one that never ends. Put on the same way a record
	 *  is, so it lands wherever the person has said sound should go. */
	function tune(station: Card) {
		queue.play([
			{
				id: -station.id,
				position: 1,
				title: station.title,
				artist: String(station.subtitle ?? ''),
				album: station.title,
				cover_url: station.image ?? null,
				duration_s: null,
				release_id: null,
				channels: 2,
				url: station.url ?? null,
				play_url: station.play_url ?? null,
				live: true
			}
		]);
	}
</script>

<!-- No heading of its own: the head above names this shelf and counts it, the
     same as every other shelf in the section. -->
<section class="shelf" class:tv={surface.isTv}>
	<Grid cards={stations} onpick={tune} />
</section>
