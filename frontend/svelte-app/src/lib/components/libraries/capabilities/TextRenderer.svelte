<!--
  @component TextRenderer
  Capability renderer for ``Capability.TEXT`` — full markdown body of an
  imported item. Uses the same sanitised renderer ItemContentModal uses so
  the styling and security posture stay consistent.

  Props:
    - payload: { mime, body } returned by getItemContentByCapability(..., 'text')
    - item:    optional LibraryItem (currently unused; kept for parity with
               the other renderers and future hooks)
-->
<script>
	import { renderMarkdownStrict } from '$lib/utils/sanitize';
	import { _ } from '$lib/i18n';
	import { EmptyState } from '$lib/components/ui';
	import { FileText } from 'lucide-svelte';

	/**
	 * @type {{ payload?: { mime?: string, body?: unknown }, item?: any }}
	 */
	let { payload = { mime: '', body: '' }, item = null } = $props();

	// The capability endpoint returns text/markdown bodies as raw strings.
	// JSON-shaped TEXT payloads aren't expected, but if one ever shows up we
	// stringify defensively so the user sees something rather than nothing.
	let raw = $derived(
		typeof payload?.body === 'string' ? payload.body : JSON.stringify(payload?.body ?? '')
	);
	let html = $derived(raw ? renderMarkdownStrict(raw) : '');
</script>

{#if raw}
	<!-- eslint-disable-next-line svelte/no-at-html-tags -->
	<div class="prose prose-sm max-w-none">{@html html}</div>
{:else}
	<EmptyState
		size="sm"
		icon={FileText}
		title={$_('libraries.itemContentModal.empty', { default: 'No content available' })}
	/>
{/if}
