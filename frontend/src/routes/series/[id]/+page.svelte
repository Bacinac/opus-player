<script lang="ts">
	import { page } from '$app/state';
	import Series from '$lib/screens/Series.svelte';
</script>

<Series id={Number(page.params.id)} />
