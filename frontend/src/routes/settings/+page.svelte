<script lang="ts">
	// What belongs to the person in front of this screen, and nothing else: what
	// they read the product in, what they want to hear, and the way out.
	//
	// The disks, where the library answers, how the sound is wired and what every
	// other profile asked for describe the machine or the rest of the house. None
	// of that is a setting of the person's; it is the installation's, and an
	// installation is maintained rather than preferred. It is one page away, behind
	// the only question this one does not ask: who keeps the place.

	import { t } from '$lib/i18n';
	import { Button, Heading, request, toasts } from '$lib/kit';
	import { me, Preferences } from '$lib/opus';
	import {
		captions,
		CAPTION_SIZES,
		CAPTION_PLACES,
		CAPTION_BACKDROPS
	} from '$lib/keep/captions.svelte';
	import Vault from '$lib/screens/Vault.svelte';
	import { forgetKeys } from '$lib/keep/vault.svelte';
	import { goto } from '$app/navigation';
	import { watching } from '$lib/keep/watching.svelte';
	import { formatBytes } from '$lib/i18n';
	import type { Profile } from '$lib/keep/types';
	import { surface } from '$lib/keep/surface.svelte';
	import Wants from '$lib/parts/Wants.svelte';
	import Cars from '$lib/parts/Cars.svelte';
	import History from '$lib/parts/History.svelte';

	// What is on the shelf to install, or nothing when no app has been built for
	// this install. The section is absent rather than empty in that case: an
	// offer to install something that is not there is worse than no offer.
	type Shelf = { versionName: string; bytes: number };
	let app = $state<Shelf | null>(null);
	// the second app on the shelf: the one the car runs, offered the same way
	let music = $state<Shelf | null>(null);
	// no app built for this install answers 404, which is an answer
	const shelf = (meta: string) => request<Shelf>(meta, {}, { on: { 404: () => {} } });
	$effect(() => {
		void (async () => {
			[app, music] = await Promise.all([shelf('/api/app/apk.json'), shelf('/api/app/music.json')]);
		})();
	});

	let mine = $state<Profile | null>(null);

	async function load() {
		const [who, people] = await Promise.all([
			request<{ profile?: Profile | null }>('/api/auth/session'),
			request<Profile[]>('/api/users')
		]);
		// the profile that was picked is who is watching; the list is what knows
		// the answers it gave, which the session does not carry
		const key = who?.profile?.key ?? '';
		mine = (people ?? []).find((p) => p.key === key) ?? null;
	}

	async function leave() {
		await forgetKeys().catch((why) => toasts.error(t('vault.forgetFailed', { detail: String(why) })));
		if (await request('/api/auth/logout', { method: 'POST' })) location.href = '/';
	}

	$effect(() => {
		load();
	});
</script>

<section>
	<Preferences />
</section>

{#if mine}
	<section>
		<Heading label={t('settings.mine')} />
		<Wants who={mine} onchanged={load} />
	</section>
{/if}

{#if mine && !surface.isTv}
	<section>
		<Heading label={t('history.title')} />
		<History />
	</section>
{/if}

<!-- Which language a subtitle is in belongs to the person and is asked above.
     How it looks belongs to the screen it is read from, which is why this one
     is not on the card about you and says whose it is. -->
<section>
	<Heading label={t('captions.title')} />
	<p class="said">{t('captions.whose')}</p>

	<h3>{t('captions.size')}</h3>
	<div class="choices">
		{#each CAPTION_SIZES as size (size)}
			<Button selected={captions.size === size} onclick={() => captions.set({ size })}>
				{t(`captions.sizes.${size}` as 'captions.sizes.small')}
			</Button>
		{/each}
	</div>

	<h3>{t('captions.place')}</h3>
	<div class="choices">
		{#each CAPTION_PLACES as place (place)}
			<Button selected={captions.place === place} onclick={() => captions.set({ place })}>
				{t(`captions.places.${place}` as 'captions.places.picture')}
			</Button>
		{/each}
	</div>
	<p class="said">{t('captions.placeWhy')}</p>

	<h3>{t('captions.backdrop')}</h3>
	<div class="choices">
		{#each CAPTION_BACKDROPS as backdrop (backdrop)}
			<Button selected={captions.backdrop === backdrop} onclick={() => captions.set({ backdrop })}>
				{t(`captions.backdrops.${backdrop}` as 'captions.backdrops.none')}
			</Button>
		{/each}
	</div>
</section>

{#if watching.person && !surface.isTv}
	<section>
		<!-- Not a way of looking at the family album, which is what a row of
		     pills beside Years and People made it look like. One person's own
		     corner, kept rather than browsed, standing with the rest of what
		     belongs to them. It names itself, so this section does not. -->
		<Vault />
	</section>
{/if}

{#if app && !surface.isTv}
	<section>
		<Heading label={t('settings.app')} />
		<p class="said">{t('settings.appWhy')}</p>
		<div class="app">
			<!-- The square is the point. Telling somebody an address to type into
			     a phone is how the app does not get installed; a camera is
			     already in their hand. -->
			<img class="square" src="/api/app/qr.svg" alt={t('settings.appQr')} />
			<div class="about">
				<Button tone="accent" href="/api/app/opus.apk">{t('settings.appGet')}</Button>
				<span class="said">
					{t('settings.appVersion', { version: app.versionName, size: formatBytes(app.bytes) })}
				</span>
			</div>
		</div>
	</section>
{/if}

{#if (music || watching.person) && !surface.isTv}
	<section>
		<Heading label={t('settings.music')} />
		{#if music}
			<p class="said">{t('settings.musicWhy')}</p>
			<div class="app">
				<div class="about">
					<Button tone="accent" href="/api/app/opus-music.apk">{t('settings.musicGet')}</Button>
					<span class="said">
						{t('settings.appVersion', { version: music.versionName, size: formatBytes(music.bytes) })}
					</span>
				</div>
			</div>
		{/if}
		{#if watching.person}<Cars />{/if}
	</section>
{/if}

{#if me.admin && !surface.isTv}
	<section>
		<!-- named, because the account that came through the door is not the
		     profile the header shows: this page belongs to whoever is watching,
		     and this one link belongs to whoever opened it -->
		<a href="/settings/house">{t('settings.house')}</a>
		<span class="whose">{watching.person}</span>
	</section>
{/if}

<section class="ways">
	<!-- Both ways out, side by side, because from the doorway they look alike
	     and they are not: one puts the question of who is watching back and
	     costs nothing, the other ends the session and asks for a password. -->
	<Button onclick={() => (watching.again(), goto('/'))}>{t('profiles.switch')}</Button>
	<Button onclick={leave}>{t('account.logout')}</Button>
</section>

<style>
	.ways {
		display: flex;
		gap: 1.5rem;
		align-items: center;
	}

	.app {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.square {
		width: 9rem;
		height: 9rem;
		color: var(--text);
		background: var(--surface);
		padding: 0.5rem;
		border-radius: 0.5rem;
	}

	.about {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.4rem;
	}

	.said {
		color: var(--muted);
		font-size: var(--fs-m);
	}

	h3 {
		margin: 0.9rem 0 0.4rem;
		font-size: var(--fs-l);
		font-weight: 600;
	}

	.choices {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.whose {
		color: var(--muted);
		font-size: var(--fs-m);
		margin-left: 0.5rem;
	}

	/* the same rhythm every other page has: a small label over its own block,
	   no ground of its own, nothing boxed */
	section {
		margin: 0 0 1.8rem;
		max-width: 52rem;
	}
</style>
