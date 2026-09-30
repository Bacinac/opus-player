<script lang="ts">
	// A person's own corner of the photographs. Not another view of the family
	// library — a different library, with one reader.
	//
	// The screen has four states and they are not steps in a wizard: there is no
	// vault yet, there is one and it is locked, it is open, or this browser
	// cannot do the arithmetic at all. The last one is said plainly rather than
	// discovered as a stack trace, because over plain http it is the truth.

	import { ArmedButton, Button, Card, Dialog, Field, Icon, json, Progress, request } from '$lib/kit';
	import { formatBytes, formatDate, formatNumber, t } from '$lib/i18n';
	import { available, b64, recoveryCode } from '$lib/ask/crypto';
	import { backup } from '$lib/keep/backup.svelte';
	import { answered, vault, type Item } from '$lib/keep/vault.svelte';
	import Wall from '$lib/tvui/Wall.svelte';
	import { MOSAIC } from '$lib/tvui/cells';
	import { watching } from '$lib/keep/watching.svelte';

	let secret = $state('');
	let code = $state('');
	let written = $state(false);
	let keep = $state(true);
	let byCode = $state(false);
	let busy = $state(false);
	let problem = $state('');
	let held = $state({ files: 0, complete: 0, bytes: 0 });

	let picker = $state<HTMLInputElement>();
	let walker = $state<HTMLInputElement>();

	// iOS says yes and then sends nothing, so ask the platform, not the attribute.
	const canWalk =
		typeof document !== 'undefined' &&
		'webkitdirectory' in document.createElement('input') &&
		!/iPad|iPhone|iPod/.test(navigator.userAgent);
	const madeCode = available() ? recoveryCode() : '';

	// what a grid cell is showing, kept so the object URLs can be let go
	const shown = new Map<string, string>();
	let opened = $state<Item | null>(null);
	let openedUrl = $state('');

	// offering is the one thing here done to several pictures at once, so the
	// grid has a second mood rather than a second screen
	let choosing = $state(false);
	let chosen = $state<Set<string>>(new Set());
	let offering = $state(0);
	let offered = $state('');

	start();

	async function start() {
		if (!available()) return;
		problem = '';
		try {
			vault.of(watching.person);
			await vault.ask();
			if (vault.enrolled && (await vault.resume())) await after();
		} catch (why) {
			problem = why instanceof Error ? why.message : String(why);
		}
	}

	async function after() {
		await vault.read();
		held = await vault.weight();
	}

	async function guard(work: () => Promise<void>) {
		busy = true;
		problem = '';
		try {
			await work();
		} catch (why) {
			problem = why instanceof Error ? why.message : String(why);
		} finally {
			busy = false;
		}
	}

	const make = () =>
		guard(async () => {
			await vault.enrol(secret, madeCode, keep);
			secret = '';
			await after();
		});

	const unlock = () =>
		guard(async () => {
			try {
				await vault.unlock(byCode ? code : secret, byCode ? 'code' : 'password', keep,
					byCode ? secret : undefined);
			} catch (why) {
				if (why instanceof DOMException && why.name === 'OperationError') throw new Error(t('vault.wrongKey'));
				throw why;
			}
			secret = code = '';
			await after();
		});

	// A camera roll walked whole also yields .thumbnails and .trashed, and the
	// tiles in there are honest JPEGs that no type check would stop.
	const carried = (f: File) =>
		!f.webkitRelativePath.split('/').some((part) => part.startsWith('.')) &&
		(/^(image|video)\//.test(f.type) || /\.(hei[cf]|dng|arw|cr[23]|nef|raf)$/i.test(f.name));

	const add = () =>
		guard(async () => {
			const files = [...(picker?.files ?? []), ...[...(walker?.files ?? [])].filter(carried)];
			if (picker) picker.value = '';
			if (walker) walker.value = '';
			if (files.length) await backup.put(files);
			held = await vault.weight();
		});

	async function thumb(item: Item, node: HTMLImageElement) {
		if (!item.thumb) return;
		const url = await vault.picture(item);
		shown.set(item.id, url);
		node.src = url;
	}

	function picture(node: HTMLImageElement, item: Item) {
		thumb(item, node).catch((why) => (problem = why instanceof Error ? why.message : String(why)));
		return {
			destroy() {
				const url = shown.get(item.id);
				if (url) URL.revokeObjectURL(url);
				shown.delete(item.id);
			}
		};
	}

	async function look(item: Item) {
		await guard(async () => {
			const blob = await vault.whole(item);
			if (openedUrl) URL.revokeObjectURL(openedUrl);
			openedUrl = URL.createObjectURL(blob);
			opened = item;
		});
	}

	function close() {
		if (openedUrl) URL.revokeObjectURL(openedUrl);
		openedUrl = '';
		opened = null;
	}

	const save = (item: Item) =>
		guard(async () => {
			const blob = await vault.whole(item);
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = item.told.name;
			link.click();
			URL.revokeObjectURL(url);
		});

	const drop = (item: Item) =>
		guard(async () => {
			await answered(`/api/photos/vault/${item.id}`, { method: 'DELETE' });
			close();
			await after();
		});

	function pick(item: Item) {
		const next = new Set(chosen);
		if (next.has(item.id)) next.delete(item.id);
		else next.add(item.id);
		chosen = next;
	}

	/** Give the household a copy. The vault keeps its own — a picture deleted
	 * from the shared library must never take somebody's backup with it. */
	const give = () =>
		guard(async () => {
			const wanted = vault.items.filter((i) => chosen.has(i.id) && i.at >= i.bytes);
			let added = 0;
			let already = 0;
			offering = wanted.length;
			for (const item of wanted) {
				// the key to this one picture, not the picture: it is already on
				// the server, sealed, and it is about to stop being private by
				// its owner's own decision
				const said = await request<{ known: boolean }>(
					`/api/photos/vault/${item.id}/offer`,
					json({
						key: b64(await vault.contentKey(item)),
						base: item.told.base,
						name: item.told.name
					})
				);
				if (!said) continue;
				if (said.known) already++;
				else added++;
				offering--;
			}
			offering = 0;
			chosen = new Set();
			choosing = false;
			await vault.read();
			offered = t('vault.offered', {
				n: formatNumber(added),
				had: formatNumber(already)
			});
		});

	const day = (told: { taken: string }) => formatDate(told.taken);
</script>

{#if !available()}
	<Card title={t('vault.title')}>
		<p class="says">{t('vault.insecure')}</p>
	</Card>
{:else if vault.enrolled === null}
	{#if problem}
		<p class="problem">{problem}</p>
		<Button onclick={start}>{t('vault.again')}</Button>
	{:else}
		<p class="says">{t('vault.asking')}</p>
	{/if}
{:else if !vault.enrolled}
	<Card title={t('vault.make')}>
		<p class="says">{t('vault.whatItIs')}</p>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				make();
			}}
			novalidate
		>
			<Field
				id="v-pass"
				type="password"
				label={t('vault.yourPassword')}
				bind:value={secret}
				autocomplete="current-password"
			/>
			<div class="code">
				<span class="label">{t('vault.recoveryCode')}</span>
				<code>{madeCode}</code>
				<p class="says small">{t('vault.recoveryWhy')}</p>
			</div>
			<label class="check">
				<input type="checkbox" bind:checked={written} />
				{t('vault.wroteItDown')}
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={keep} />
				{t('vault.keepHere')}
			</label>
			{#if problem}<p class="problem">{problem}</p>{/if}
			<Button type="submit" tone="primary" disabled={!secret || !written || busy}>
				{busy ? t('vault.making') : t('vault.make')}
			</Button>
		</form>
	</Card>
{:else if !vault.open}
	<Card title={t('vault.locked')}>
		{#if !vault.kept}
			<!-- Why it is asking. Without this the screen reads as a dead end to
			     somebody who told another device to remember the key. -->
			<p class="says small">{t('vault.noKeyHere')}</p>
		{/if}
		{#if vault.kept}
			<!-- The key is on this device, so the way back in is a press. Asking
			     for the password here would be asking somebody to prove again
			     what they told this phone to remember. -->
			<div class="row">
				<Button
					tone="primary"
					disabled={busy}
					onclick={() =>
						guard(async () => {
							if (await vault.resume()) await after();
							else problem = t('vault.wrongKey');
						})}
				>
					{busy ? t('vault.opening') : t('vault.unlock')}
				</Button>
				<Button disabled={busy} onclick={() => guard(() => vault.forget())}>{t('vault.forget')}</Button>
			</div>
		{/if}
		<form
			onsubmit={(e) => {
				e.preventDefault();
				unlock();
			}}
			novalidate
		>
			{#if byCode}
				<Field id="v-code" label={t('vault.recoveryCode')} bind:value={code} autocomplete="off" />
				<Field
					id="v-new"
					type="password"
					label={t('vault.setPassword')}
					bind:value={secret}
					autocomplete="new-password"
				/>
				<p class="says small">{t('vault.codeRewraps')}</p>
			{:else}
				<Field
					id="v-open"
					type="password"
					label={t('vault.yourPassword')}
					bind:value={secret}
					autocomplete="current-password"
				/>
			{/if}
			<label class="check">
				<input type="checkbox" bind:checked={keep} />
				{t('vault.keepHere')}
			</label>
			{#if problem}<p class="problem">{problem}</p>{/if}
			<div class="row">
				<Button type="submit" tone="primary" disabled={busy}>
					{busy ? t('vault.opening') : t('vault.unlock')}
				</Button>
				<Button onclick={() => ((byCode = !byCode), (problem = ''))}>
					{byCode ? t('vault.usePassword') : t('vault.useCode')}
				</Button>
			</div>
		</form>
	</Card>
{:else}
	<div class="head">
		<div class="counts">
			<strong>{formatNumber(held.files)}</strong>
			<span>{t('vault.files')}</span>
			<strong>{formatBytes(held.bytes)}</strong>
		</div>
		<div class="row">
			<!-- no accept: on Android it is what tells the system to open the
			     gallery picker, which hands over a copy with the location
			     stripped out of the EXIF. Without it the same input goes through
			     the document provider and the original arrives whole. -->
			<input bind:this={picker} type="file" multiple onchange={add} hidden />
			<Button tone="primary" disabled={backup.running} onclick={() => picker?.click()}>
				{t('vault.add')}
			</Button>
			<!-- A whole camera roll is months of folders, and the picker above
			     reaches into one at a time. This one walks the tree instead.
			     Safari on iOS reports the attribute and then hands back nothing,
			     so the button only appears where the walk actually happens. -->
			{#if canWalk}
				<input bind:this={walker} type="file" multiple webkitdirectory onchange={add} hidden />
				<Button disabled={backup.running} onclick={() => walker?.click()}>
					{t('vault.addFolder')}
				</Button>
			{/if}
			<Button
				onclick={() => {
					choosing = !choosing;
					chosen = new Set();
					offered = '';
				}}
			>
				{choosing ? t('vault.stopChoosing') : t('vault.choose')}
			</Button>
			<Button onclick={() => vault.lock()}>{t('vault.lock')}</Button>
		</div>
	</div>

	{#if backup.running || backup.stage === 'done' || backup.stage === 'failed'}
		<div class="doing">
			{#if backup.running}
				<span class="what">{backup.now || t('vault.working')}</span>
				<span class="tally">
					{formatNumber(backup.done + backup.skipped + backup.failed)} / {formatNumber(
						backup.total
					)}
				</span>
				{#if backup.of}
					<span class="bar"><Progress value={backup.sent / backup.of} /></span>
				{/if}
				<Button onclick={() => backup.halt()}>{t('vault.stop')}</Button>
			{:else}
				<span class="what">
					{t('vault.putAway', { n: formatNumber(backup.done) })}
					{#if backup.skipped}
						· {t('vault.alreadyHad', { n: formatNumber(backup.skipped) })}
					{/if}
					{#if backup.failed}
						· <span class="warn">{t('vault.wouldNot', { n: formatNumber(backup.failed) })}</span>
					{/if}
				</span>
				{#if backup.trouble}<span class="warn">{backup.trouble}</span>{/if}
			{/if}
		</div>
	{/if}

	{#if choosing}
		<div class="doing">
			<span class="what">
				{chosen.size ? t('vault.chosen', { n: formatNumber(chosen.size) }) : t('vault.chooseSome')}
			</span>
			{#if offering}<span class="tally">{formatNumber(offering)}</span>{/if}
			<Button tone="primary" disabled={!chosen.size || busy} onclick={give}>
				{t('vault.offer')}
			</Button>
		</div>
	{:else if offered}
		<div class="doing"><span class="what">{offered}</span></div>
	{/if}

	{#if problem}<p class="problem">{problem}</p>{/if}
	{#if vault.unreadable}
		<p class="problem">{t('vault.unreadable', { n: formatNumber(vault.unreadable) })}</p>
	{/if}

	{#if vault.reading}
		<p class="says">{t('vault.opening')}</p>
	{:else if !vault.items.length && !vault.unreadable}
		<p class="says">{t('vault.empty')}</p>
	{:else}
		<Wall cell={MOSAIC.cell} gap={MOSAIC.gap}>
			{#snippet children(_across)}
			{#each vault.items as item (item.id)}
				<button
					class="cell"
					class:picked={chosen.has(item.id)}
					onclick={() => (choosing ? pick(item) : look(item))}
					title={item.told.name}
					aria-label={item.told.name}
				>
					{#if item.thumb}
						<img use:picture={item} alt={item.told.name} />
					{:else}
						<span class="none"><Icon name={item.told.type.startsWith('video/') ? 'clip' : 'photo'} size={22} /></span>
					{/if}
					{#if item.at < item.bytes}<span class="partial">{t('vault.partial')}</span>{/if}
					{#if item.photo_id}<span class="given">{t('vault.given')}</span>{/if}
					{#if choosing}<span class="tick">{#if chosen.has(item.id)}<Icon name="check" size={12} />{/if}</span>{/if}
				</button>
			{/each}
			{/snippet}
		</Wall>
	{/if}
{/if}

{#if opened}
	{@const item = opened}
	<Dialog
		title={item.told.name}
		subtitle={`${day(item.told)} · ${formatBytes(item.told.bytes)}`}
		size="wide"
		onclose={close}
	>
		{#snippet actions()}
			<Button size="small" onclick={() => save(item)}>{t('vault.save')}</Button>
			<ArmedButton size="small" onconfirm={() => drop(item)}>{t('vault.remove')}</ArmedButton>
		{/snippet}
		{#if item.told.type.startsWith('video/')}
			<!-- svelte-ignore a11y_media_has_caption -->
			<video class="whole" src={openedUrl} controls></video>
		{:else}
			<img class="whole" src={openedUrl} alt={item.told.name} />
		{/if}
	</Dialog>
{/if}

<style>
	.says {
		color: var(--muted);
		font-size: var(--fs-m);
		margin: 0 0 0.8rem;
		max-width: 40rem;
		line-height: 1.5;
	}
	.small {
		font-size: var(--fs-s);
	}
	form {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		align-items: flex-start;
		max-width: 26rem;
	}
	.code {
		margin: 0.5rem 0 0.2rem;
	}
	.label {
		display: block;
		font-size: var(--fs-s);
		color: var(--muted);
		margin-bottom: 0.25rem;
	}
	code {
		display: inline-block;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
		font-size: var(--fs-l);
		letter-spacing: 0.08em;
		font-variant-numeric: tabular-nums;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: var(--fs-m);
	}
	.row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		align-items: center;
	}
	.problem {
		color: var(--warn);
		font-size: var(--fs-m);
		margin: 0.2rem 0;
	}
	.warn {
		color: var(--warn);
	}
	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
		margin-bottom: 0.9rem;
	}
	.counts {
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		color: var(--muted);
		font-size: var(--fs-m);
	}
	.counts strong {
		color: var(--text);
		font-variant-numeric: tabular-nums;
	}
	.doing {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		flex-wrap: wrap;
		padding: 0.55rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--surface);
		margin-bottom: 0.9rem;
		font-size: var(--fs-m);
	}
	.what {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 22rem;
	}
	.tally {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.bar {
		flex: 1;
		min-width: 6rem;
	}
	.cell {
		position: relative;
		aspect-ratio: 1;
		padding: 0;
		border: 0;
		background: var(--surface);
		cursor: pointer;
		overflow: hidden;
	}
	.cell img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.none {
		display: grid;
		place-items: center;
		width: 100%;
		height: 100%;
		color: var(--muted);
	}
	.cell.picked {
		outline: 3px solid var(--accent);
		outline-offset: -3px;
	}
	.tick {
		position: absolute;
		right: 5px;
		top: 5px;
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 999px;
		border: 2px solid var(--on-picture);
		background: var(--veil-thin);
		color: var(--on-picture);
		display: grid;
		place-items: center;
	}
	.given {
		position: absolute;
		right: 4px;
		bottom: 4px;
		padding: 0.05rem 0.35rem;
		border-radius: 999px;
		background: var(--surface);
		color: var(--muted);
		font-size: var(--fs-xs);
	}
	.partial {
		position: absolute;
		left: 4px;
		bottom: 4px;
		padding: 0.05rem 0.35rem;
		border-radius: 999px;
		background: var(--warn);
		color: var(--surface);
		font-size: var(--fs-xs);
	}
	.whole {
		display: block;
		max-width: 100%;
		max-height: 72vh;
		margin: 0 auto;
		object-fit: contain;
		border-radius: var(--radius-s);
		background: var(--picture-ground);
	}
</style>
