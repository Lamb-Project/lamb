<!--
  @component FilterChip
  A small pill representing a single active filter with an "×" clear button.
  Clicking the × calls onClear — does not affect other chips.
-->
<script>
	import { _ } from '$lib/i18n';

	/**
	 * @type {{ id: string, label: string, value: string, onClear: () => void }}
	 */
	let { label, value, onClear } = $props();
</script>

<span
	class="border-info bg-info-50 text-info inline-flex items-center gap-1 rounded-full border py-0.5 pr-1.5 pl-2.5 text-xs font-medium"
>
	<span class="text-info">{label}:</span>
	<span>{value}</span>
	<button
		type="button"
		onclick={onClear}
		aria-label="{$_('list.filters.removeFilter')} {label}"
		class="text-muted hover:bg-info-100 hover:text-info ml-0.5 rounded-full p-0.5 focus:outline-none"
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
