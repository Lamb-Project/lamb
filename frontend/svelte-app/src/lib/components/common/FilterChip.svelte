<!--
  @component FilterChip
  A small pill representing a single active filter with an "×" clear button.
  Clicking the × calls onClear — does not affect other chips.
-->
<script>
	/**
	 * @type {{ id: string, label: string, value: string, onClear: () => void }}
	 */
	let { label, value, onClear } = $props();
</script>

<span
	class="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 py-0.5 pr-1.5 pl-2.5 text-xs font-medium text-blue-800"
>
	<span class="text-blue-500">{label}:</span>
	<span>{value}</span>
	<button
		type="button"
		onclick={onClear}
		aria-label="Remove {label} filter"
		class="ml-0.5 rounded-full p-0.5 text-blue-400 hover:bg-blue-100 hover:text-blue-600 focus:outline-none"
	>
		<svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M6 18L18 6M6 6l12 12"
			/>
		</svg>
	</button>
</span>
