<script lang="ts">
	// Where somebody keeps what they listened to and watched, if they keep it
	// anywhere: their own ListenBrainz for records, their own Simkl for films and
	// television. Linked here once; from then on what the player counts as heard
	// or seen goes there too, and what could not go is said here.

	import { ArmedButton, Button, Field, json, request, toasts } from '$lib/kit';
	import { me } from '$lib/opus';
	import { formatNumber, t } from '$lib/i18n';

	type Service = {
		service: 'listenbrainz' | 'simkl';
		account: string | null;
		waiting: number;
		unknown: number;
		problem: string;
	};
	type Linked = { simkl_ready: boolean; services: Service[] };
	type Code = {
		device_code: string;
		user_code: string;
		verification_uri: string;
		verification_uri_complete: string;
		expires_in: number;
		interval: number;
	};

	const NAMES = {
		listenbrainz: { name: 'history.listenbrainz', what: 'history.listenbrainz.what' },
		simkl: { name: 'history.simkl', what: 'history.simkl.what' }
	} as const;

	let linked = $state<Linked | null>(null);
	let token = $state('');
	let code = $state<Code | null>(null);
	let asking: ReturnType<typeof setTimeout> | null = null;

	async function load() {
		linked = await request<Linked>('/api/history');
	}

	async function linkListenbrainz() {
		const said = await request<Linked>('/api/history/listenbrainz', json({ token: token.trim() }, 'PUT'), {
			on: { 400: () => toasts.error(t('history.listenbrainz.refused')) }
		});
		if (!said) return;
		linked = said;
		token = '';
	}

	/** Simkl's way for an app with no page of its own to come back to: a code
	 *  approved on their site, and this asking every few seconds whether it has
	 *  been yet. A refusal never comes back as one — the code only runs out —
	 *  so the asking stops at its own deadline. */
	async function linkSimkl() {
		code = await request<Code>('/api/history/simkl/code', json({}));
		if (code) wait(code, code.interval, Date.now() + code.expires_in * 1000);
	}

	function wait(given: Code, every: number, until: number) {
		asking = setTimeout(async () => {
			if (code !== given) return;
			if (Date.now() > until) {
				code = null;
				return toasts.error(t('history.simkl.expired'));
			}
			const said = await request<{ linked: boolean; slower?: boolean; ended?: string }>(
				'/api/history/simkl/token',
				json({ device_code: given.device_code })
			);
			if (code !== given) return;
			if (said && !said.linked && !said.ended) return wait(given, said.slower ? every + 5 : every, until);
			code = null;
			if (said?.ended) toasts.error(t('history.simkl.expired'));
			if (said?.linked) {
				toasts.success(t('history.simkl.linked'));
				await load();
			}
		}, every * 1000);
	}

	async function unlink(service: Service['service']) {
		if (await request(`/api/history/${service}`, { method: 'DELETE' })) await load();
	}

	async function retry() {
		if (await request('/api/history/retry', { method: 'POST' })) await load();
	}

	$effect(() => {
		void load();
		return () => {
			if (asking) clearTimeout(asking);
		};
	});
</script>

{#if linked}
	{#each linked.services as one (one.service)}
		<div class="service">
			<h3>{t(NAMES[one.service].name)}</h3>
			<p class="said">{t(NAMES[one.service].what)}</p>
			{#if one.account}
				<div class="row">
					<span>{t('history.linkedAs', { account: one.account })}</span>
					<ArmedButton onconfirm={() => unlink(one.service)}>{t('history.unlink')}</ArmedButton>
				</div>
				{#if one.waiting || one.unknown}
					<p class="said">
						{#if one.waiting}{t('history.waiting', { count: formatNumber(one.waiting) })}{/if}
						{#if one.problem}{t('history.problem', { detail: one.problem })}{/if}
						{#if one.unknown}{t('history.unknown', { count: formatNumber(one.unknown) })}{/if}
					</p>
					<Button onclick={retry}>{t('history.retry')}</Button>
				{/if}
			{:else if one.service === 'listenbrainz'}
				<form
					class="row"
					onsubmit={(event) => {
						event.preventDefault();
						void linkListenbrainz();
					}}
				>
					<Field
						id="listenbrainz-token"
						type="password"
						autocomplete="off"
						label={t('history.listenbrainz.token')}
						bind:value={token}
					/>
					<Button tone="accent" type="submit" disabled={!token.trim()}>{t('history.link')}</Button>
				</form>
				<a class="said" href="https://listenbrainz.org/settings/" target="_blank" rel="noreferrer">
					{t('history.listenbrainz.where')}
				</a>
			{:else if !linked.simkl_ready}
				<p class="said">{t(me.admin ? 'history.simkl.setUp' : 'history.simkl.askAdmin')}</p>
			{:else if code}
				<p>
					{t('history.simkl.enter', { url: code.verification_uri })}
					<a href={code.verification_uri_complete} target="_blank" rel="noreferrer" class="code">
						{code.user_code}
					</a>
				</p>
			{:else}
				<Button tone="accent" onclick={linkSimkl}>{t('history.link')}</Button>
			{/if}
		</div>
	{/each}
{/if}

<style>
	.service {
		display: grid;
		gap: 0.5rem;
		justify-items: start;
		margin: 0 0 1.2rem;
	}
	h3 {
		margin: 0;
		font-size: var(--fs-m);
		font-weight: 600;
	}
	.row {
		display: flex;
		align-items: end;
		flex-wrap: wrap;
		gap: 0.8rem;
	}
	.said {
		margin: 0;
		color: var(--muted);
		font-size: var(--fs-m);
	}
	.code {
		display: block;
		margin-top: 0.4rem;
		font-size: var(--fs-xl);
		font-weight: 600;
		letter-spacing: 0.2em;
	}
</style>
