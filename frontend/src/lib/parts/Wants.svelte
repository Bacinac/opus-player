<script lang="ts">
	// The answers a profile gives about what it wants to hear and to read, in
	// order — the second is what a film with no Croatian sound comes up in — and
	// whose photographs a box's screensaver shows while it is picked there.
	//
	// Drawn wherever a profile is — the person's own settings, and the roster an
	// admin keeps — because they are the same answers about the same thing,
	// and a second copy of them is the copy that drifts.

	import { t } from '$lib/i18n';
	import Choose from '$lib/tvui/Choose.svelte';
	import Rows from '$lib/tvui/Rows.svelte';
	import { json, request } from '$lib/kit';
	import { me } from '$lib/opus';
	import { faces, type Face } from '$lib/ask/photos';
	import type { Profile } from '$lib/keep/types';

	let { who, onchanged }: { who: Profile; onchanged: () => void } = $props();

	// what this house actually watches in; the rest is a list nobody reads
	const LANGUAGES = [
		{ code: 'hr', label: 'Hrvatski' },
		{ code: 'en', label: 'English' },
		{ code: 'de', label: 'Deutsch' },
		{ code: 'it', label: 'Italiano' },
		{ code: 'fr', label: 'Français' },
		{ code: 'es', label: 'Español' }
	];

	type Kind = 'audio_languages' | 'subtitle_languages';

	const KINDS: { field: Kind; label: string; none: string }[] = $derived([
		{ field: 'audio_languages', label: t('profiles.audio'), none: t('profiles.asFound') },
		{ field: 'subtitle_languages', label: t('profiles.subtitle'), none: t('play.subtitlesOff') }
	]);

	/** Which of the two answers is being given, and what the pair becomes. An
	 *  emptied first choice promotes the second: a preference with a hole at the
	 *  top of it is not an order. */
	function reorder(current: string, rank: 0 | 1, code: string): string {
		const pair = current.split(',').filter(Boolean);
		pair[rank] = code;
		return pair.filter(Boolean).join(',');
	}

	const choiceOf = (order: string | null | undefined, rank: 0 | 1) =>
		(order ?? '').split(',').filter(Boolean)[rank] ?? '';

	let family = $state<Face[]>([]);
	$effect(() => {
		if (me.guest) return;
		void faces().then((people) => (family = people.filter((p) => p.family)));
	});

	// whoever the profile is stands first, and is what an untouched profile
	// shows; one the library has no face for starts at the family. Several
	// people may share the screen; the family stands alone, being all of them
	const own = $derived(family.find((p) => p.account === who.key));
	const called = (p: Face) => p.given_name || p.name;
	const screensavers = $derived([
		...[...(own ? [own] : []), ...family.filter((p) => p !== own)].map((p) => ({
			key: String(p.id),
			label: called(p)
		})),
		{ key: 'household', label: t('profiles.household') }
	]);
	const screensaver = $derived.by(() => {
		const said = who.screensaver ?? '';
		if (said) return said.split(',');
		return own ? [String(own.id)] : ['household'];
	});

	function showing(key: string): string {
		if (key === 'household') return 'household';
		const people = screensaver.filter((k) => k !== 'household');
		const now = people.includes(key) ? people.filter((k) => k !== key) : [...people, key];
		return now.length === 1 && own && now[0] === String(own.id) ? '' : now.join(',');
	}

	async function set(field: Kind | 'screensaver', value: string) {
		const saved = await request(
			`/api/users/${encodeURIComponent(who.key)}`,
			json({ [field]: value }, 'PATCH')
		);
		if (saved) onchanged();
	}
</script>

<Rows>
	{#each KINDS as kind (kind.field)}
		{#each [0, 1] as rank (rank)}
			<div class="row">
				<span class="what">
					{kind.label}
					<em>{rank === 0 ? t('profiles.first') : t('profiles.then')}</em>
				</span>
				<Choose
					said=""
					chosen={[choiceOf(who[kind.field], rank as 0 | 1)]}
					options={[
						{ key: '', label: rank === 0 ? kind.none : t('profiles.nothing') },
						...LANGUAGES.map((l) => ({ key: l.code, label: l.label }))
					]}
					onpick={(code) =>
						set(kind.field, reorder(who[kind.field] ?? '', rank as 0 | 1, code))}
				/>
			</div>
		{/each}
	{/each}
	{#if family.length}
		<div class="row">
			<span class="what">{t('profiles.screensaver')}</span>
			<Choose
				said=""
				many
				chosen={screensaver}
				options={screensavers}
				onpick={(key) => set('screensaver', showing(key))}
			/>
		</div>
	{/if}
</Rows>
