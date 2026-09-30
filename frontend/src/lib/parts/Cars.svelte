<script lang="ts">
	// The cars that can still play from this house: each one paired once with a
	// password, and each one taken back here without touching the others or the
	// password. An admin sees every one; anybody else sees their own.

	import { ArmedButton, request } from '$lib/kit';
	import { me } from '$lib/opus';
	import { formatDateTime, t } from '$lib/i18n';

	type Car = { id: number; person: string; created_at: string; last_seen_at: string | null };

	let cars = $state<Car[] | null>(null);

	async function load() {
		const said = await request<{ cars: Car[] }>('/api/auth/cars');
		cars = said?.cars ?? [];
	}

	async function takeBack(car: Car) {
		if (await request(`/api/auth/cars/${car.id}`, { method: 'DELETE' })) await load();
	}

	$effect(() => {
		void load();
	});
</script>

{#if cars?.length}
	<ul>
		{#each cars as car (car.id)}
			<li>
				<span class="said">
					{#if me.admin}<strong>{car.person}</strong>{/if}
					{t('cars.paired', { date: formatDateTime(car.created_at) })}
					{#if car.last_seen_at}· {t('cars.seen', { date: formatDateTime(car.last_seen_at) })}{/if}
				</span>
				<ArmedButton onconfirm={() => takeBack(car)}>{t('cars.remove')}</ArmedButton>
			</li>
		{/each}
	</ul>
{:else if cars}
	<p class="said">{t('cars.none')}</p>
{/if}

<style>
	ul {
		list-style: none;
		margin: 0.8rem 0 0;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}
	li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	.said {
		color: var(--muted);
		font-size: var(--fs-m);
	}
	strong {
		color: var(--text);
		font-weight: 600;
		margin-right: 0.4rem;
	}
</style>
