<script lang="ts">
	import { page } from '$app/state';
	import { HelpPage } from '$lib/kit';
	import { helpFor } from '$lib/opus';
</script>

<HelpPage help={helpFor('player')} slug={page.params.slug ?? ''} />
