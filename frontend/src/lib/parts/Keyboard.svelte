<script lang="ts">
	// Typing with a remote.
	//
	// A text field is a dead end on a television: the D-pad reaches it and then
	// has nothing to say to it. So the letters are on the screen and the same
	// arrows that walk a shelf walk them — which is what every set-top box does,
	// Kodi included.

	import { i18n, t } from '$lib/i18n';
	import { toasts } from '$lib/kit';
	import { onBox } from '$lib/tv/bridge';

	let { value, hint, onchange, onsubmit }: {
		value: string;
		/** what goes in the box before anything is typed: what this search looks for */
		hint: string;
		onchange: (next: string) => void;
		onsubmit: () => void;
	} = $props();

	// The arrangement everybody already knows the shape of. Alphabetical grids
	// are what set-top boxes reach for and nobody can find a letter on one —
	// the hand knows where S is on this and does not on that. Croatian letters
	// sit at the end of the rows they belong to, and the numbers run along the
	// top the way they do on a real one.
	const ROWS = [
		'1234567890',
		'QWERTZUIOP',
		'ASDFGHJKLČĆ',
		'YXCVBNMŠĐŽ'
	];

	const type = (ch: string) => onchange(value + ch);
	const SPACE = ' ';

	// Speaking instead of spelling, where the box has a recognizer: what it hears
	// goes into the box while it is said, and what it ends on is searched for.
	const hears = onBox((box) => box.hears?.() ?? false) ?? false;
	const SPEECH = { hr: 'hr-HR', en: 'en-US' } as const;
	let listening = $state(false);
	let heard = $state('');

	function listen() {
		heard = '';
		listening = true;
		onBox((box) => box.listen?.(SPEECH[i18n.locale]));
	}

	// the recognizer's error numbers, as somebody holding a remote can act on them
	function fault(code: number): string {
		if ([1, 2, 4, 11].includes(code)) return t('keys.voice.offline');
		if (code === 9) return t('keys.voice.refused');
		if (code === 12 || code === 13) return t('keys.voice.language');
		return t('keys.voice.failed', { code: String(code) });
	}

	$effect(() => {
		if (!hears) return;
		window.opusListen = listen;
		window.opusHeard = (said) => {
			if ('text' in said) {
				heard = said.text;
				if (!said.done) return;
			}
			listening = false;
			if ('error' in said) toasts.error(fault(said.error));
			else if (!('text' in said) || !said.text) toasts.info(t('keys.voice.unheard'));
			else {
				onchange(said.text);
				onsubmit();
			}
		};
		onBox((box) => box.voiceKey?.(true));
		return () => {
			onBox((box) => {
				box.voiceKey?.(false);
				box.stopListening?.();
			});
			delete window.opusListen;
			delete window.opusHeard;
		};
	});
</script>

<div class="board">
	<p class="typed">
		{listening ? heard || t('keys.voice.listening') : value || hint}<span class="caret"></span>
	</p>
	{#each ROWS as row, r (r)}
		<div class="row">
			{#each row.split('') as ch (ch)}
				<button onclick={() => type(ch)}>{ch}</button>
			{/each}
		</div>
	{/each}
	<div class="row wide">
		{#if hears}
			<button class:go={listening} onclick={listen}>{t('keys.voice.speak')}</button>
		{/if}
		<button onclick={() => type(SPACE)}>{t('keys.space')}</button>
		<button onclick={() => onchange(value.slice(0, -1))}>{t('keys.back')}</button>
		<button onclick={() => onchange('')}>{t('keys.clear')}</button>
		<button class="go" onclick={onsubmit}>{t('explore.find')}</button>
	</div>
</div>

<style>
	.board {
		display: grid;
		gap: 0.35rem;
		padding: 0.6rem;
		border-radius: var(--radius-m);
		background: var(--surface);
		border: 1px solid var(--border);
	}
	.typed {
		margin: 0 0 0.3rem;
		padding: 0.35rem 0.5rem;
		min-height: 1.4em;
		border-radius: 6px;
		background: color-mix(in srgb, var(--bg) 70%, transparent);
		color: var(--text);
		font-size: var(--fs-l);
		word-break: break-word;
	}
	.caret {
		display: inline-block;
		width: 1px;
		height: 1em;
		margin-left: 1px;
		vertical-align: -0.15em;
		background: var(--muted);
	}
	/* rows of different lengths, each key the same size, the row centred under
	   the one above — which is what a keyboard looks like */
	.row {
		display: flex;
		justify-content: center;
		gap: 0.3rem;
	}
	.row button {
		flex: 1 1 0;
		min-width: 0;
	}
	.row.wide {
		margin-top: 0.4rem;
	}
	button {
		aspect-ratio: 1;
		display: grid;
		place-items: center;
		padding: 0;
		border-radius: 8px;
		border: 1px solid transparent;
		background: color-mix(in srgb, var(--surface-2) 70%, transparent);
		color: inherit;
		font: inherit;
		line-height: 1;
		cursor: pointer;
		transition:
			background 120ms ease,
			transform 120ms ease;
	}
	.row.wide button {
		aspect-ratio: auto;
		padding: 0.5rem 0;
		font-size: var(--fs-m);
	}
	button:focus-visible {
		outline: none;
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 32%, transparent);
		transform: scale(1.12);
	}
	.go {
		background: color-mix(in srgb, var(--accent) 35%, transparent);
	}
</style>
