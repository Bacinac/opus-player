<script lang="ts">
	import { t } from '$lib/i18n';
	import type { Hardness, Standing as Row } from '$lib/ask/guess';
	import Press from '$lib/tvui/Press.svelte';
	import Standing from '$lib/parts/Standing.svelte';

	let {
		how,
		quiet,
		busy,
		standing,
		mine,
		onharden,
		onhush,
		onbegin
	}: {
		how: Hardness;
		quiet: boolean;
		busy: boolean;
		standing: Row[];
		mine: string;
		onharden: (how: Hardness) => void;
		onhush: () => void;
		onbegin: () => void;
	} = $props();

	const STEPS: { key: Hardness; say: () => string }[] = [
		{ key: 'easy', say: () => t('guess.how.easy') },
		{ key: 'fair', say: () => t('guess.how.fair') },
		{ key: 'hard', say: () => t('guess.how.hard') }
	];
</script>

<!-- The same word whether it is on or off: the colour is the answer, the way it
     is for the step of difficulty. Written once and stood in two places, because
     where it belongs depends on how much room there is — beside the difficulty
     where a row has space for both, and with Play where it does not, since
     stacked above the three steps it reads as one of them. -->
{#snippet speaker()}
	<Press tone={quiet ? 'plain' : 'go'} onclick={onhush}>{t('guess.sound')}</Press>
{/snippet}

<div class="intro">
	<p class="what">{t('guess.what')}</p>
	<div class="how">
		<span class="says">{t('guess.how')}</span>
		<!-- written out rather than built from the key: a key that is
		     assembled is a key the words check cannot see, and a word nobody
		     can prove is asked for is a word that quietly goes missing -->
		{#each STEPS as step (step.key)}
			<Press tone={how === step.key ? 'go' : 'plain'} onclick={() => onharden(step.key)}>
				{step.say()}
			</Press>
		{/each}
		<span class="wide">{@render speaker()}</span>
	</div>
	<div class="begin">
		<Press tone="go" disabled={busy} onclick={onbegin}>{t('guess.play')}</Press>
		<span class="narrow">{@render speaker()}</span>
	</div>
	{#if standing.length}
		<h3>{t('guess.standing')}</h3>
		<Standing {standing} {mine} best />
	{/if}
</div>

<style>
	.how {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.9rem;
	}

	.how .says {
		color: var(--muted);
		margin-right: 0.3rem;
	}

	/* set apart from the three it stands beside: it answers a different
	   question, and a fourth box in the same run would read as a fourth step */
	.how .wide {
		display: contents;
	}

	.how .wide :global(button) {
		margin-left: 1.6rem;
	}

	.narrow {
		display: none;
	}

	.intro {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 44rem;
		padding: 1rem 0 2rem;
	}

	/* On a phone this was six stacked blocks and a row that broke in half, so
	   the sound sat alone on a line of its own and Play was a third of the way
	   down the screen. Two rows do the same work: what it is asked over what
	   there is to choose. */
	@media (max-width: 560px) {
		.intro {
			gap: 0.7rem;
			padding-top: 0.5rem;
		}

		.what {
			font-size: var(--fs-m);
			line-height: 1.45;
		}

		.how {
			margin-bottom: 0;
		}

		/* the whole line to itself, so the three steps below it are three equal
		   thirds and not two with a stray one beside the label */
		.how .says {
			flex: 0 0 100%;
			margin: 0;
		}

		.how > :global(.press) {
			flex: 1 1 0;
		}

		.how .wide {
			display: none;
		}

		.narrow {
			display: contents;
		}

		.begin :global(button) {
			flex: 1;
		}
	}
	.what {
		color: var(--muted);
		margin: 0;
		line-height: 1.5;
	}
	.begin {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}
</style>
