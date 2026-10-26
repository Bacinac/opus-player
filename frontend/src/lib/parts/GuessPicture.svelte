<script lang="ts">
	import type { Question, Rect } from '#lib/ask/guess.js';

	let {
		src,
		frame = null,
		marked = false,
		hide = null,
		zoom = null,
		zooming = false,
		seconds = 20
	}: {
		src: string;
		/** the face asked about, framed on the picture when `marked` */
		frame?: Rect | null;
		marked?: boolean;
		/** the patch over whoever is missing, while they are */
		hide?: Rect | null;
		/** where a detail starts and how far in; the picture opens out from
		 *  there over the whole clock while `zooming`, and snaps whole after */
		zoom?: Question['zoom'];
		zooming?: boolean;
		seconds?: number;
	} = $props();

	/* Where a fraction of the picture sits on the screen, which is not where it
	   sits in the file: the picture is drawn contained, so it is letterboxed
	   inside the stage and anything laid over it has to be put back on the
	   pixels that were painted. Measured off the picture the browser actually
	   painted, not off the dimensions the catalogue holds: those are the
	   original's, and a photograph the camera wrote sideways is not the shape
	   of its own row. */
	let stageW = $state(0);
	let stageH = $state(0);
	let natural = $state({ w: 0, h: 0 });
	const painted = $derived.by(() => {
		if (!natural.w || !natural.h || !stageW || !stageH) return null;
		const scale = Math.min(stageW / natural.w, stageH / natural.h);
		const w = natural.w * scale;
		const h = natural.h * scale;
		return { left: (stageW - w) / 2, top: (stageH - h) / 2, w, h };
	});
	const placed = (rect: Rect | null | undefined) => {
		if (!rect || !painted) return null;
		return {
			left: painted.left + rect.x * painted.w,
			top: painted.top + rect.y * painted.h,
			width: rect.w * painted.w,
			height: rect.h * painted.h
		};
	};
	const marker = $derived(placed(frame));
	const cover = $derived(placed(hide));

	/* The detail. The picture starts scaled up around the point asked for and
	   is let out to its whole self over the clock; a frame after it is put up,
	   so the transition has a start to leave from. Not while revealed: then it
	   snaps whole, and a reveal that slid would be a reveal still being asked. */
	let wide = $state(false);
	$effect(() => {
		void src;
		void zoom;
		wide = false;
		const soon = requestAnimationFrame(() => requestAnimationFrame(() => (wide = true)));
		return () => cancelAnimationFrame(soon);
	});
	const origin = $derived.by(() => {
		if (!zoom) return 'center';
		if (!painted) return `${zoom.x * 100}% ${zoom.y * 100}%`;
		return `${painted.left + zoom.x * painted.w}px ${painted.top + zoom.y * painted.h}px`;
	});
	const transform = $derived(
		zoom && zooming && !wide ? `scale(${zoom.scale})` : zoom && zooming ? 'scale(1)' : 'none'
	);
</script>

<div class="stage" class:zooming={!!zoom && zooming} bind:clientWidth={stageW} bind:clientHeight={stageH}>
	<img
		{src}
		alt=""
		style:transform-origin={origin}
		style:transform
		style:transition-duration={zoom && zooming && wide ? `${seconds}s` : '0s'}
		onload={(e: Event) => {
			const img = e.currentTarget as HTMLImageElement;
			natural = { w: img.naturalWidth, h: img.naturalHeight };
		}}
	/>
	{#if cover}
		<span
			class="cover"
			style:left="{cover.left}px"
			style:top="{cover.top}px"
			style:width="{cover.width}px"
			style:height="{cover.height}px"
		><span>?</span></span>
	{/if}
	{#if marker && marked}
		<span
			class="marker"
			style:left="{marker.left}px"
			style:top="{marker.top}px"
			style:width="{marker.width}px"
			style:height="{marker.height}px"
		></span>
	{/if}
</div>

<style>
	/* The picture is given what is left of the screen and no more. A stage that
	   takes its natural height puts the answers below the fold, and a question
	   with a clock on it that has to be scrolled to is not a question. */
	.stage {
		position: relative;
		flex: 1 1 auto;
		/* whatever the question, the answers and the reveal line leave over */
		min-height: 0;
		overflow: hidden;
	}
	.stage img {
		width: 100%;
		height: 100%;
		object-fit: contain;
		transition-property: transform;
		transition-timing-function: linear;
	}
	/* Not a highlight: a bracket around whoever is being asked about, so a
	   picture with somebody standing beside them still has one answer. */
	.marker {
		position: absolute;
		border: 2px solid var(--accent);
		border-radius: 6px;
		box-shadow: 0 0 0 9999px color-mix(in srgb, var(--bg) 35%, transparent);
		pointer-events: none;
	}
	/* Opaque, not blurred. A blur leaves the hair, the skin and the shape of the
	   head, and in a family that is half the answer; the patch leaves only the
	   gap, which is the question. */
	.cover {
		position: absolute;
		display: grid;
		place-items: center;
		background: color-mix(in srgb, var(--bg) 88%, var(--text));
		border-radius: 45% / 35%;
		box-shadow: 0 0 18px 10px color-mix(in srgb, var(--bg) 88%, var(--text));
		color: var(--muted);
		font-weight: 700;
		font-size: var(--fs-2xl);
		pointer-events: none;
	}
	:global(html.tv) .stage {
		grid-area: stage;
		min-height: 0;
	}
</style>
