<script lang="ts">
	import type { Question } from '$lib/ask/guess';

	let { src, frame, marked }: { src: string; frame: Question['frame']; marked: boolean } = $props();

	/* Where the face sits on the screen, which is not where it sits in the
	   file: the picture is drawn contained, so it is letterboxed inside the
	   stage and the box has to be put back on the pixels that were painted. */
	let stageW = $state(0);
	let stageH = $state(0);
	let natural = $state({ w: 0, h: 0 });
	const marker = $derived.by(() => {
		// measured off the picture the browser actually painted, not off the
		// dimensions the catalogue holds: those are the original's, and a
		// photograph the camera wrote sideways is not the shape of its own row
		if (!frame || !natural.w || !natural.h || !stageW || !stageH) return null;
		const scale = Math.min(stageW / natural.w, stageH / natural.h);
		const shown = { w: natural.w * scale, h: natural.h * scale };
		const left = (stageW - shown.w) / 2 + frame.x * shown.w;
		const top = (stageH - shown.h) / 2 + frame.y * shown.h;
		return { left, top, width: frame.w * shown.w, height: frame.h * shown.h };
	});
</script>

<div class="stage" bind:clientWidth={stageW} bind:clientHeight={stageH}>
	<img
		{src}
		alt=""
		onload={(e: Event) => {
			const img = e.currentTarget as HTMLImageElement;
			natural = { w: img.naturalWidth, h: img.naturalHeight };
		}}
	/>
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
	}
	.stage img {
		width: 100%;
		height: 100%;
		object-fit: contain;
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
	:global(html.tv) .stage {
		grid-area: stage;
		min-height: 0;
	}
</style>
