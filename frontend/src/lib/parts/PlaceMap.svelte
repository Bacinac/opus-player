<script lang="ts">
	// Where the house has been, on a map you step across rather than drag.
	//
	// A television has four arrows and an OK, and panning a map with them is
	// punishment: you are steering a camera to look for something you can already
	// see. So the arrows move between the **places** — the nearest one in the
	// direction pressed — and the map follows whichever is chosen. The same
	// behaviour serves a mouse, which simply clicks the one it wants.
	//
	// The pins are sized by how much happened there. A week on one beach and an
	// afternoon in a town should not look alike, and the size says which is which
	// before any label is read.

	import { onMount } from 'svelte';
	import { surface } from '$lib/keep/surface.svelte';
	import { formatNumber, t } from '$lib/i18n';
	import type { Where } from '$lib/ask/photos';
	import Press from '$lib/tvui/Press.svelte';

	let {
		places,
		onopen,
		glance = false
	}: {
		places: Where[];
		onopen?: (place: string) => void;
		/** where one place lies, for orientation only: nothing to step between
		 *  and nothing to press, so the remote never stops on it */
		glance?: boolean;
	} = $props();

	type Pin = Where & { lat: number; lon: number };

	// only what can be drawn: a place with no coordinate is a name the map has
	// nowhere to put, and it is still reachable in the list beside this
	const pins = $derived(
		places
			.map((p) => ({ ...p, lat: p.at?.lat ?? NaN, lon: p.at?.lon ?? NaN }))
			.filter((p): p is Pin => Number.isFinite(p.lat) && Number.isFinite(p.lon))
	);

	let box = $state<HTMLDivElement>();
	let here = $state(0);
	let ready = $state(false);
	let map: import('leaflet').Map | null = null;
	let marks: import('leaflet').CircleMarker[] = [];
	let L: typeof import('leaflet') | null = null;

	/** How big a pin is: by the square root of what happened there, so a place
	 *  with a hundred times as many photographs is ten times as wide rather than
	 *  a hundred, which would be a blot over half of Europe. */
	const radius = (n: number) => Math.max(5, Math.min(26, Math.sqrt(n) * 1.1));

	onMount(() => {
		let gone = false;
		void (async () => {
			// Leaflet touches `window` as it loads, and this page is rendered on the
			// server first — so it arrives when there is a browser to arrive into.
			const leaflet = (await import('leaflet')).default;
			await import('leaflet/dist/leaflet.css');
			if (gone || !box) return;
			L = leaflet;
			map = L.map(box, {
				zoomControl: !surface.isTv && !glance,
				attributionControl: true,
				// the arrows belong to the places; dragging is for a hand
				keyboard: false,
				scrollWheelZoom: !surface.isTv
			});
			L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
				maxZoom: 18,
				attribution: '© OpenStreetMap',
				// the page's same-origin policy sends OSM no Referer at all, and OSM
				// answers a tile asked for without one with a 403 picture; the origin
				// alone is what its usage policy asks for
				referrerPolicy: 'strict-origin-when-cross-origin'
			}).addTo(map);

			draw();
			ready = true;
		})();
		return () => {
			gone = true;
			map?.remove();
			map = null;
			marks = [];
		};
	});

	$effect(() => {
		void pins.length;
		if (ready) draw();
	});

	function draw() {
		if (!map || !L) return;
		marks.forEach((m) => m.remove());
		// drawn as SVG attributes, where a custom property is not resolved
		const ink = getComputedStyle(box!).getPropertyValue('--kind-photos').trim();
		marks = pins.map((p, i) =>
			L!
				.circleMarker([p.lat, p.lon], {
					radius: radius(p.photographs),
					weight: 2,
					color: ink,
					fillColor: ink,
					fillOpacity: 0.45
				})
				.addTo(map!)
				.on('click', () => choose(i, true))
		);
		if (glance && pins.length) {
			// a country's worth around it: close enough to say which coast, far
			// enough to say which country
			map.setView([pins[0].lat, pins[0].lon], 6);
		} else if (pins.length) {
			map.fitBounds(
				L.latLngBounds(pins.map((p) => [p.lat, p.lon] as [number, number])),
				{ padding: [40, 40] }
			);
			choose(0, false);
		}
	}

	function choose(i: number, open: boolean) {
		here = i;
		marks.forEach((m, n) =>
			m.setStyle({ fillOpacity: n === i ? 0.9 : 0.45, weight: n === i ? 4 : 2 })
		);
		const p = pins[i];
		if (p && map) map.panTo([p.lat, p.lon], { animate: true });
		if (open && p) onopen?.(p.place);
	}

	/** The nearest place in the direction pressed. Nearest by how far it is,
	 *  among those that are actually that way — a step to the right that landed
	 *  on something above would be a map that argues with the remote. */
	function step(dx: number, dy: number) {
		const from = pins[here];
		if (!from) return;
		let best = -1;
		let cost = Infinity;
		pins.forEach((p, i) => {
			if (i === here) return;
			// east is +lon, north is +lat; the screen's y runs the other way
			const along = dx ? (p.lon - from.lon) * dx : (from.lat - p.lat) * dy;
			if (along <= 0) return;
			const across = Math.abs(dx ? p.lat - from.lat : p.lon - from.lon);
			const c = along + across * 2.5;
			if (c < cost) {
				cost = c;
				best = i;
			}
		});
		if (best >= 0) choose(best, false);
	}

	function key(e: KeyboardEvent) {
		const go: Record<string, [number, number]> = {
			ArrowRight: [1, 0],
			ArrowLeft: [-1, 0],
			ArrowUp: [0, 1],
			ArrowDown: [0, -1]
		};
		if (e.key in go) {
			e.preventDefault();
			step(...go[e.key]);
		} else if (e.key === 'Enter' && pins[here]) {
			e.preventDefault();
			onopen?.(pins[here].place);
		}
	}
</script>

{#if glance}
	<div class="map glance" aria-hidden="true" inert>
		<div class="canvas" bind:this={box}></div>
	</div>
{:else}
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
	class="map"
	class:tv={surface.isTv}
	role="application"
	aria-label={t('photos.places')}
	tabindex="0"
	onkeydown={key}
>
	<div class="canvas" bind:this={box}></div>

	{#if pins[here]}
		<div class="said">
			<strong>{pins[here].place}</strong>
			<span>{t('count.photos.many', { n: formatNumber(pins[here].photographs) })}</span>
			<Press tone="pill" onclick={() => onopen?.(pins[here].place)}>{t('photos.open')}</Press>
		</div>
	{/if}
</div>
{/if}

<style>
	.map {
		position: relative;
		outline: none;
	}
	.canvas {
		height: min(62vh, 32rem);
		border-radius: 12px;
		overflow: hidden;
		background: var(--surface);
	}
	.tv .canvas {
		height: 66vh;
	}
	.glance .canvas {
		height: 100%;
		pointer-events: none;
	}
	.glance {
		width: 100%;
		height: 100%;
	}
	.map:focus-visible .canvas {
		outline: 3px solid var(--accent);
		outline-offset: 2px;
	}
	.said {
		position: absolute;
		left: 0.9rem;
		bottom: 0.9rem;
		z-index: 500;
		display: flex;
		align-items: center;
		gap: 0.7rem;
		padding: 0.5rem 0.8rem;
		border-radius: var(--radius-pill);
		border: 1px solid var(--border);
		background: var(--bg);
	}
	.tv .said {
		font-size: var(--fs-xl);
		padding: 0.7rem 1.1rem;
	}
	.said span {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
</style>
