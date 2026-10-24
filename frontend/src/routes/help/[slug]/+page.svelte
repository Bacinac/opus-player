<script lang="ts">
	import { page } from '$app/state';
	import { HelpPage } from '#lib/kit/index.js';
	import { helpFor } from '#lib/opus/index.js';
</script>

<HelpPage help={helpFor('player')} slug={page.params.slug ?? ''} />
