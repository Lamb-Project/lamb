<!--
  @component ItemContentModal
  Modal chrome wrapping the shared ItemContentTabs component. Used by the
  items table on LibraryDetail; the new FileTreeModal renders ItemContentTabs
  directly in its preview pane.
-->
<script>
	import { _, locale } from '$lib/i18n';
	import ItemContentTabs from './ItemContentTabs.svelte';
	import { Modal, Button } from '$lib/components/ui';

	let {
		isOpen = $bindable(false),
		isLoading = $bindable(false),
		title = '',
		content = '',
		/** @type {string|null} */
		error = null,
		sourceType = '',
		sourceUrl = '',
		originalFilename = '',
		libraryId = '',
		itemId = '',
		/** @type {(() => void) | null} */
		onviewOriginal = null,
		onclose = () => {}
	} = $props();

	let localeLoaded = $derived(!!$locale);

	function close() {
		onclose();
		isOpen = false;
	}
</script>

<Modal
	open={isOpen}
	onclose={close}
	size="xl"
	title={title ||
		(localeLoaded
			? $_('libraries.itemContentModal.title', { default: 'Item Content' })
			: 'Item Content')}
	closeAriaLabel={$_('common.close', { default: 'Close' })}
	bodyClass="p-0"
>
	<!--
		``flex flex-col`` here is required so the child ItemContentTabs
		(which uses ``h-full`` internally) resolves its height against
		a real flex container — otherwise the inner overflow-y-auto
		never bounds and the markdown view can't scroll. The parent
		``Modal`` body already constrains height via flex-1, so we
		don't impose our own ``max-h``.
	-->
	<div class="flex h-full min-h-0 flex-col">
		<ItemContentTabs
			{libraryId}
			{itemId}
			{isLoading}
			{content}
			{error}
			{sourceType}
			{sourceUrl}
			{originalFilename}
			{onviewOriginal}
			resetKey={itemId}
		/>
	</div>
	{#snippet footer({ close: closeFn })}
		<Button variant="secondary" onclick={closeFn}>
			{localeLoaded ? $_('libraries.itemContentModal.close', { default: 'Close' }) : 'Close'}
		</Button>
	{/snippet}
</Modal>
