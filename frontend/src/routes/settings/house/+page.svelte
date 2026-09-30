<script lang="ts">
	// The machine and the house: room left on the disks, who lives here and what
	// each of them asked for, and the plumbing that says how DIDA is reached and
	// how the sound is wired.
	//
	// None of it is a preference. It is what somebody maintains, which is a
	// different job from watching a film, and it is why this is a page of its own
	// rather than the bottom half of somebody's settings — a member reading their
	// own two answers has no business being shown the roster and the wiring, and
	// showing them made the account that maintains the install look like a person
	// with unusually many opinions.

	import { goto } from '$app/navigation';
	import { formatBytes, t, type MessageKey } from '$lib/i18n';
	import {
		ArmedButton,
		Button,
		Card,
		Heading,
		Meter,
		SaveBar,
		SettingField,
		SettingsDraft,
		json,
		request
	} from '$lib/kit';
	import {
		me,
		Tokens
	} from '$lib/opus';
	import type { Profile, Volume } from '$lib/keep/types';
	import { COLOURS } from '$lib/tvui/colours';
	import Portrait from '$lib/tvui/Portrait.svelte';
	import Wants from '$lib/parts/Wants.svelte';
	import Wiring, { type Wired } from '$lib/parts/Wiring.svelte';

	let people = $state<Profile[]>([]);
	let adding = $state('');
	// the form to name somebody stays shut until it is asked for
	let naming = $state(false);
	let plumbing = $state(false);
	let volumes = $state<Volume[]>([]);
	const form = new SettingsDraft();

	// what the audio settings can point at, asked of DIDA in the house's own
	// words — a device is picked by its name, never typed by its designation
	type Choice = { value: string; label: string };
	type CastOptions = { media: Choice[]; sources: string[]; boxes: Choice[] };
	let castOpts = $state<CastOptions | null>(null);
	let castProblem = $state('');

	const ENTITY_KEYS = new Set([
		'audio_output_stereo',
		'audio_output_multi',
		'audio_volume_entity',
		'audio_amp_entity'
	]);
	const SOURCE_KEYS = new Set(['audio_amp_source']);

	async function loadCastOptions() {
		castProblem = '';
		castOpts = await request<CastOptions>('/api/cast/options', {}, {
			failed: (detail) => (castProblem = detail)
		});
	}

	function choicesFor(key: string): Choice[] | undefined {
		if (!castOpts) return undefined;
		if (ENTITY_KEYS.has(key)) return castOpts.media;
		if (SOURCE_KEYS.has(key)) return castOpts.sources.map((s) => ({ value: s, label: s }));
		if (key === 'tv_box') return castOpts.boxes;
		// the house's own devices only: our screen and our DAC lead the list, and
		// the house cannot wake either of them
		if (key === 'tv_box_entity') return castOpts.media.filter((c) => c.value !== 'tv' && c.value !== 'dac');
		return undefined;
	}

	const groups = $derived([...new Set(form.settings.map((f) => f.group))]);

	let wiring = $state<{ sources: string[]; boxes: Wired[] } | null>(null);

	async function load() {
		const [list, disks, wired] = await Promise.all([
			request<Profile[]>('/api/users'),
			request<{ volumes?: Volume[] }>('/api/storage'),
			request<{ sources: string[]; boxes: Wired[] }>('/api/cast/boxes'),
			form.load()
		]);
		people = list ?? [];
		volumes = disks?.volumes ?? [];
		wiring = wired;
	}

	async function addProfile(event: Event) {
		event.preventDefault();
		const made = await request(
			'/api/users',
			json({ name: adding, colour: COLOURS[people.length % COLOURS.length] })
		);
		if (!made) return;
		adding = '';
		naming = false;
		await load();
	}

	async function removeProfile(who: Profile) {
		if (await request(`/api/users/${encodeURIComponent(who.key)}`, { method: 'DELETE' })) await load();
	}

	// The door already refuses everything behind this page; the address is what
	// is left, and an address that draws an empty frame is worse than one that
	// takes you back where you came from. A television is inside as a box and is
	// nobody, which is a no here as well.
	$effect(() => {
		if (me.open && !me.admin) {
			goto('/settings', { replaceState: true });
			return;
		}
		if (me.admin) load();
	});
</script>

{#if me.admin}
	<section>
		<a href="/settings">← {t('settings.title')}</a>
	</section>

	{#if volumes.length}
		<section>
			<Heading label={t('settings.storage')} />
			<div class="disks">
				{#each volumes as v (v.path)}
					<Meter
						label={v.holds.map((h) => t(`storage.${h}` as MessageKey)).join(' · ')}
						used={v.used}
						total={v.total}
						note={t('settings.storageFree', { free: formatBytes(v.free), path: v.path })}
					/>
				{/each}
			</div>
		</section>
	{/if}

	<section>
		<Heading label={t('settings.profiles')} />
		<ul>
			{#each people as who (who.key)}
				<li>
					<Portrait rung="mark" hue={who.colour || undefined} name={who.name} />
					<span class="name">{who.name}</span>
					<!-- Somebody on the roster exists next door and is removed next door.
					     Only a profile that is nobody's account is this screen's to take
					     away, and taking it away loses a colour and a language order,
					     never a person. -->
					{#if !who.roster}
						<ArmedButton onconfirm={() => removeProfile(who)}>{t('profiles.remove')}</ArmedButton>
					{/if}

					<div class="rows">
						<Wants {who} onchanged={load} />
					</div>
				</li>
			{/each}
		</ul>

		{#if naming}
			<form class="naming" onsubmit={addProfile}>
				<input bind:value={adding} placeholder={t('profiles.name')} required />
				<Button tone="primary" type="submit">{t('profiles.add')}</Button>
				<Button onclick={() => (naming = false)}>{t('common.cancel')}</Button>
			</form>
		{:else}
			<Button tone="primary" onclick={() => (naming = true)}>{t('profiles.add')}</Button>
		{/if}
	</section>

	{#if wiring?.boxes.length}
		<section>
			<Heading label={t('settings.boxes')} />
			<p class="muted">{t('settings.boxesHint')}</p>
			<Wiring sources={wiring.sources} boxes={wiring.boxes} onchanged={load} />
		</section>
	{/if}

	<section>
		<Button
			onclick={() => {
				plumbing = !plumbing;
				if (plumbing && !castOpts) loadCastOptions();
			}}
		>
			{plumbing ? t('settings.hidePlumbing') : t('settings.showPlumbing')}
		</Button>
	</section>

	{#if plumbing}
		<form
			class="plumbing"
			onsubmit={(event) => {
				event.preventDefault();
				form.save();
			}}
		>
			{#each groups as group (group)}
				<Card title={t(`settings.group.${group}` as MessageKey)}>
					<p class="muted">{t(`settings.hint.${group}` as MessageKey)}</p>
					{#if group === 'audio' && castProblem}
						<p class="muted">{t('settings.didaDown', { detail: castProblem })}</p>
					{/if}
					<div class="fields">
						{#each form.of(group) as setting (setting.key)}
							<SettingField
								{setting}
								bind:value={form.draft[setting.key]}
								choices={choicesFor(setting.key)}
							/>
						{/each}
					</div>
				</Card>
			{/each}
			<Card title={t('account.token')}>
				<Tokens />
			</Card>
			<SaveBar dirty={form.dirty} saving={form.saving} />
		</form>
	{/if}
{/if}

<style>
	/* the same rhythm every other page has: a small label over its own block,
	   no ground of its own, nothing boxed */
	section {
		margin: 0 0 1.8rem;
		max-width: 52rem;
	}
	ul {
		list-style: none;
		margin: 0 0 0.9rem;
		padding: 0;
		display: grid;
		gap: 0.7rem;
	}
	/* a person is a block, not a line: their name across the top and the four
	   answers they gave underneath, which is what fits on a television. No box
	   around it — nothing on any other page is boxed. */
	li {
		display: grid;
		grid-template-columns: auto 1fr auto auto;
		align-items: center;
		gap: 0.5rem 0.7rem;
		padding: 0.2rem 0 1rem;
		border-bottom: 1px solid color-mix(in srgb, var(--border) 40%, transparent);
	}
	.rows {
		grid-column: 1 / -1;
		margin-top: 0.3rem;
	}

	.name {
		flex: 1;
	}
	.naming {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.plumbing {
		display: grid;
		gap: 1rem;
		max-width: 52rem;
	}
</style>
