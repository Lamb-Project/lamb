<script>
	import '../app.css';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50 font-sans text-gray-900">
	{@render children()}
</div>
