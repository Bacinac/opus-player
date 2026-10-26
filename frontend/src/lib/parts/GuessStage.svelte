<script lang="ts" module>
	import type { Question as Asked } from '#lib/ask/guess.js';
	import { cropOf as crop, previewOf as preview } from '#lib/opus/index.js';

	/** Every picture of a round, now, before the first question is asked — and
	 *  the face as well where one is asked about, because that is what goes up
	 *  first and the photograph only follows the answer. A game with a clock
	 *  on it cannot also have a spinner. */
	export function warm(questions: Asked[]) {
		for (const one of questions) {
			new Image().src = preview(one.photo.id, one.photo.turn);
			if (one.second) new Image().src = preview(one.second.id, one.second.turn);
			if (one.kind === 'who' && one.face) new Image().src = `${crop(one.face)}?size=big`;
		}
	}
</script>

<script lang="ts">
	// One question on the stage: what is asked, the picture (or the two), the
	// answers and the clock, and under them whatever the screen has to say about
	// the answer. The same stage whether one person is playing against the
	// clock or a television is asking a room: what differs is who may press.

	import type { Snippet } from 'svelte';
	import { formatNumber, t } from '#lib/i18n/index.js';
	import { cropOf, previewOf } from '#lib/opus/index.js';
	import type { Facts, Question, Someone } from '#lib/ask/guess.js';
	import { askedOf, photoSays } from '#lib/say/says.js';
	import Answers from '#lib/tvui/Answers.svelte';
	import Press from '#lib/tvui/Press.svelte';
	import Clock from '#lib/parts/Clock.svelte';
	import GuessPicture from '#lib/parts/GuessPicture.svelte';
	import Pair from '#lib/tvui/Pair.svelte';

	let {
		question,
		at,
		count,
		score = null,
		until,
		seconds,
		revealed,
		chosen = null,
		correct = null,
		facts = null,
		secondFacts = null,
		marks = {},
		onpick,
		onnext,
		said,
		waiting
	}: {
		question: Question;
		at: number;
		count: number;
		/** the running total, where there is one of one person's */
		score?: number | null;
		until: number;
		seconds: number;
		revealed: boolean;
		chosen?: string | null;
		correct?: string | null;
		facts?: Facts | null;
		secondFacts?: Facts | null;
		/** who pressed which, once revealed — a party's */
		marks?: Record<string, Someone[]>;
		/** absent where this screen only shows */
		onpick?: (key: string) => void;
		/** on to the next question before the reveal has stood its time */
		onnext?: () => void;
		/** the verdict and whatever follows it */
		said?: Snippet;
		/** what stands in its place while the question is still open */
		waiting?: Snippet;
	} = $props();

	const picture = (photo: { id: string; turn: number }) => previewOf(photo.id, photo.turn);

	/* What is on the stage. A question about who somebody is shows the FACE:
	   the photograph around it answers the question by itself for anybody who
	   recognises the room, the day, or who else is standing there. Once it has
	   been answered the whole photograph comes up — which is what the face was
	   cut out of, and the half of it that was being kept back. */
	const showing = $derived(
		question.kind === 'who' && question.face && !revealed
			? `${cropOf(question.face)}?size=big`
			: picture(question.photo)
	);
	// the face is framed where the picture is whole and somebody in it is the
	// question: after the reveal of who or who is missing, and all along for how
	// old, since the name is given and the picture is whole
	const framed = $derived(
		question.kind === 'age' || ((question.kind === 'who' || question.kind === 'missing') && revealed)
	);

	const pairSaid = $derived(
		revealed && facts && secondFacts ? { a: photoSays(facts), b: photoSays(secondFacts) } : null
	);

	/* What is left of the window under whatever head this surface draws above
	   the game — measured, not guessed at with a viewport fraction. The round
	   must not scroll: pressing an answer near the bottom of a page taller than
	   the window scrolls it, and a question that has walked off the top is a
	   question being answered from memory. */
	let floor = $state<HTMLElement>();
	let room = $state(0);
	$effect(() => {
		const measure = () => {
			if (!floor) return;
			// what the page puts BELOW this counts too. The frame ends its main
			// with three rems of air, which is right under a shelf and is dead
			// weight under a screen already sized to the window: the round would run
			// off the bottom by exactly that much.
			const below = floor.closest('main');
			const air = below ? parseFloat(getComputedStyle(below).paddingBottom) || 0 : 0;
			room = Math.max(300, window.innerHeight - floor.getBoundingClientRect().top - air - 14);
		};
		measure();
		// after the frame the section unmounts in, or this measures the old top
		const soon = requestAnimationFrame(measure);
		window.addEventListener('resize', measure);
		return () => {
			cancelAnimationFrame(soon);
			window.removeEventListener('resize', measure);
		};
	});
</script>

<div class="round" bind:this={floor} style:height={room ? `${room}px` : undefined}>
	<header>
		<span class="asked">{askedOf(question.kind, question.name)}</span>
		<span class="where">{t('guess.of', { n: formatNumber(at + 1), total: formatNumber(count) })}</span>
		{#if score !== null}<span class="score">{formatNumber(score)}</span>{/if}
		<Clock {until} {seconds} running={!revealed} />
	</header>

	{#if question.kind === 'order' && question.second}
		<Pair
			a={question.photo}
			b={question.second}
			{chosen}
			{correct}
			{revealed}
			facts={pairSaid}
			{marks}
			{onpick}
		/>
	{:else}
		<GuessPicture
			src={showing}
			frame={question.frame}
			marked={framed}
			hide={question.kind === 'missing' && !revealed ? question.hide : null}
			zoom={question.kind === 'zoom' ? question.zoom : null}
			zooming={!revealed}
			{seconds}
		/>
		<Answers options={question.options} {chosen} {correct} {revealed} {marks} {onpick} />
	{/if}

	<!-- always there, empty while the question stands: a row that appears
	     with the answer would move the answers under the hand reaching for
	     them, and the clock is running -->
	<div class="said">
		{#if revealed}
			{@render said?.()}
			{#if facts && question.kind !== 'order'}<span class="truth">{photoSays(facts)}</span>{/if}
			{#if onnext}<Press tone="plain" onclick={onnext}>{t('guess.next')}</Press>{/if}
		{:else}
			{@render waiting?.()}
		{/if}
	</div>
</div>

<style>
	.round {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
		height: 100%;
		min-height: 0;
	}
	header {
		display: flex;
		align-items: center;
		gap: 0.9rem;
	}
	.asked {
		font-size: var(--fs-xl);
		font-weight: 600;
		flex: 1;
	}
	.where,
	.score {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.score {
		color: var(--text);
		font-weight: 600;
	}

	.said {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		flex-wrap: wrap;
		min-height: 2.6rem;
	}
	.truth {
		color: var(--muted);
		flex: 1;
	}

	:global(html.tv) .asked {
		font-size: var(--fs-2xl);
	}

	/* A television is wide, and the question was laid out down it: header over
	   picture over four answers over a line of comment, each taking its height
	   from the one above until the photograph — which is the whole question —
	   had what was left, and the column still ran off the bottom.

	   Two columns instead. The picture takes the room a sixteen-by-nine screen
	   actually has, and the answers stand beside it in one narrow rail rather
	   than in a block under it. Two pictures take both columns: lettered, they
	   are their own answers.

	   What the photograph turns out to have been is a sentence, and it gets the
	   whole width to be one in: under the picture alone it was set in the same
	   narrow column and broke into three lines while half the screen beside it
	   stood empty. */
	:global(html.tv) .round {
		display: grid;
		grid-template-columns: 1fr 30rem;
		grid-template-rows: auto minmax(0, 1fr) auto;
		grid-template-areas:
			'head head'
			'stage answers'
			'said said';
		column-gap: 2.5rem;
		row-gap: 0.9rem;
	}
	:global(html.tv) .round > header {
		grid-area: head;
	}
	:global(html.tv) .round > :global(.answers) {
		grid-area: answers;
		align-content: center;
	}
	:global(html.tv) .round > :global(.pair) {
		grid-column: 1 / -1;
		grid-row: 2;
	}
	:global(html.tv) .said {
		grid-area: said;
		font-size: var(--fs-xl);
		min-height: 3.4rem;
	}
</style>
