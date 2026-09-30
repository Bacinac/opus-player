<script lang="ts">
	// The subtitle, drawn by us rather than by the browser.
	//
	// The browser's own renderer measures a cue against the VIDEO ELEMENT and
	// anchors it to that element's bottom. Our element fills the stage and the
	// picture is letterboxed inside it, so the text came out sized off a box far
	// taller than the picture and printed into the black bar beneath it. Nothing
	// about that is settable: `::cue` reaches the size and not the place.
	//
	// So the track is switched to `hidden` — which parses the cues and fills
	// `activeCues` without drawing anything — and what it holds is painted here,
	// over the picture's own rectangle, at a size that is a share of the
	// picture's height. The cue is asked for its own HTML rather than its text:
	// italics in a subtitle say who is speaking from off-screen, and stripping
	// the markup would throw that away.

	import { captions } from '$lib/keep/captions.svelte';

	let { video, track }: { video: HTMLVideoElement | null; track: TextTrack | null } = $props();

	type Rect = { left: number; width: number; top: number; height: number; bar: number };
	let picture = $state<Rect | null>(null);
	let holder = $state<HTMLDivElement | null>(null);
	let showing = $state(false);

	/** Where the picture actually is, which `object-fit: contain` decides and
	 *  nothing reports. */
	function measure() {
		if (!video?.videoWidth || !video.videoHeight) {
			picture = null;
			return;
		}
		const r = video.getBoundingClientRect();
		const scale = Math.min(r.width / video.videoWidth, r.height / video.videoHeight);
		const width = video.videoWidth * scale;
		const height = video.videoHeight * scale;
		picture = {
			left: r.left + (r.width - width) / 2,
			width,
			top: r.top + (r.height - height) / 2,
			height,
			bar: r.bottom - (r.top + (r.height - height) / 2 + height)
		};
	}

	$effect(() => {
		if (!video) return;
		measure();
		const observer = new ResizeObserver(measure);
		observer.observe(video);
		video.addEventListener('loadedmetadata', measure);
		window.addEventListener('resize', measure);
		return () => {
			observer.disconnect();
			video.removeEventListener('loadedmetadata', measure);
			window.removeEventListener('resize', measure);
		};
	});

	/** Repaint from whatever the track holds now. A seek replaces the track
	 *  elements outright, so this follows the track it is given rather than
	 *  subscribing once. */
	$effect(() => {
		const node = holder;
		if (!node) return;
		const current = track;
		if (!current) {
			node.replaceChildren();
			showing = false;
			return;
		}
		const paint = () => {
			node.replaceChildren();
			const active = Array.from(current.activeCues ?? []) as VTTCue[];
			for (const cue of active) {
				const line = document.createElement('div');
				line.className = 'line';
				line.appendChild(cue.getCueAsHTML());
				node.appendChild(line);
			}
			showing = active.length > 0;
		};
		paint();
		current.addEventListener('cuechange', paint);
		return () => current.removeEventListener('cuechange', paint);
	});

	const size = $derived(picture ? captions.lineHeight(picture.height) : 0);

	/** How far off the bottom of the viewport the text sits.
	 *
	 *  In the bar when there is a bar to sit in and it is deep enough to hold a
	 *  line — a scope film on a 16:9 screen — and over the picture otherwise.
	 *  Asked for the bar and given none, it stays on the picture rather than
	 *  hanging off the bottom: a setting the shape of the film cannot honour is
	 *  still a picture that has to be readable. */
	const lift = $derived.by(() => {
		if (!picture) return 0;
		const below = window.innerHeight - (picture.top + picture.height);
		if (captions.place === 'below' && picture.bar >= size * 2) {
			return below - picture.bar / 2 - size;
		}
		return below + picture.height * 0.05;
	});
</script>

<!-- One element, always mounted. Swapping it for another when there is nothing
     to show would remount the node this component's own effect binds to, and an
     effect that rebinds what it writes to is a loop. It is hidden instead. -->
<div
	class="captions {captions.backdrop}"
	class:hushed={!showing || !picture}
	style:left="{picture?.left ?? 0}px"
	style:width="{picture?.width ?? 0}px"
	style:bottom="{lift}px"
	style:font-size="{size}px"
	bind:this={holder}
></div>

<style>
	.captions {
		position: fixed;
		z-index: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.15em;
		/* the picture is what is being watched; the text is never a target */
		pointer-events: none;
		text-align: center;
		text-wrap: balance;
		line-height: 1.3;
		font-weight: 600;
		color: var(--on-picture);
	}
	/* A line is its own box so that a backdrop hugs the words rather than
	   painting a band across the picture. */
	.captions :global(.line) {
		max-width: 90%;
		padding: 0.05em 0.35em;
		border-radius: 0.15em;
	}
	.shadow :global(.line) {
		/* an outline rather than a drop shadow: white on white is the case that
		   has to survive, and a shadow under the letters does not help it */
		text-shadow:
			0 0 0.12em var(--picture-ground),
			0 0 0.24em var(--picture-ground),
			0.03em 0.03em 0.06em var(--picture-ground);
	}
	.box :global(.line) {
		background: var(--veil-thick);
	}
	.hushed {
		display: none;
	}
</style>
