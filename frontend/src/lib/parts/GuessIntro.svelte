<script lang="ts">
	import { t } from '#lib/i18n/index.js';
	import type { Hardness, OpenParty, Standing as Row } from '#lib/ask/guess.js';
	import Press from '#lib/tvui/Press.svelte';
	import Standing from '#lib/parts/Standing.svelte';

	let {
		how,
		quiet,
		busy,
		standing,
		mine,
		parties = [],
		onharden,
		onhush,
		onbegin,
		ontogether,
		onresume,
		onjoin
	}: {
		how: Hardness;
		quiet: boolean;
		busy: boolean;
		standing: Row[];
		mine: string;
		/** parties open on other screens right now */
		parties?: OpenParty[];
		onharden: (how: Hardness) => void;
		onhush: () => void;
		onbegin: () => void;
		/** ask the room from this screen */
		ontogether: () => void;
		/** pick this screen's own open party back up */
		onresume: (id: number) => void;
		onjoin: (id: number) => void;
	} = $props();

	const STEPS: { key: Hardness; say: () => string }[] = [
		{ key: 'easy', say: () => t('guess.how.easy') },
		{ key: 'fair', say: () => t('guess.how.fair') },
		{ key: 'hard', say: () => t('guess.how.hard') }
	];

	const hosted = $derived(parties.find((p) => p.mine === 'host') ?? null);
	const joinable = $derived(parties.filter((p) => p.mine !== 'host'));
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

	<!-- The room. A party open on another screen is the first thing offered,
	     since somebody who came here to join should not have to read past the
	     way to host; this screen's own, left open by a reload, comes back. -->
	<div class="together">
		{#each joinable as party (party.id)}
			<Press tone="go" onclick={() => onjoin(party.id)}>
				{t('guess.join', { host: party.host?.name ?? '' })}
				{#if party.under_way}<span class="note">· {t('guess.underWay')}</span>{/if}
			</Press>
		{/each}
		{#if hosted}
			<Press tone="plain" onclick={() => onresume(hosted.id)}>{t('guess.resume')}</Press>
		{:else}
			<Press tone="plain" onclick={ontogether}>{t('guess.together')}</Press>
		{/if}
		<span class="says">{t('guess.together.what')}</span>
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

	.together {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.together .says {
		color: var(--muted);
		flex: 1 1 14rem;
	}
	.note {
		color: var(--muted);
		font-weight: 400;
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

		.begin :global(button),
		.together :global(button) {
			flex: 1 1 100%;
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
