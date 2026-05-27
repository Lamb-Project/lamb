<!--
  @component ImagesRenderer
  Capability renderer for ``Capability.IMAGES`` — gallery of extracted images.

  Uses native ``fetch`` (not axios) to load each image as a blob, then
  builds a ``blob:`` URL for ``<img src>``. Native fetch is used because
  it's the most predictable path and gives us full control over response
  handling — axios + ``responseType: 'blob'`` has had subtle quirks when
  re-issuing requests after HMR.
-->
<script>
	import { onDestroy } from 'svelte';
	import { getApiUrl } from '$lib/config';
	import { _ } from '$lib/i18n';
	import { Loader2 } from 'lucide-svelte';

	/**
	 * @typedef {{ filename: string, url?: string, mime?: string }} ImageRow
	 * @typedef {{ blobUrl?: string, error?: string, httpStatus?: number }} ImageStatus
	 */

	/** @type {{ payload?: { body?: unknown }, item?: any, libraryId?: string }} */
	let { payload = { body: [] }, item = null, libraryId = '' } = $props();

	/** @type {ImageRow[]} */
	let images = $derived(
		Array.isArray(payload?.body) ? /** @type {ImageRow[]} */ (payload.body) : []
	);

	let lib = $derived(libraryId || item?.library_id || '');
	let itemId = $derived(item?.id || '');

	/** filename → status */
	let status = $state(/** @type {Record<string, ImageStatus>} */ ({}));

	let trackedKey = '';
	let key = $derived(`${lib}|${itemId}|${images.map((i) => i.filename).join(',')}`);

	/** @param {string} filename */
	async function loadImage(filename) {
		const token = (typeof localStorage !== 'undefined' && localStorage.getItem('userToken')) || '';
		const url = getApiUrl(
			`/libraries/${lib}/items/${itemId}/content/images/file/${encodeURIComponent(filename)}`
		);
		try {
			const resp = await fetch(url, {
				headers: token ? { Authorization: `Bearer ${token}` } : {}
			});
			if (!resp.ok) {
				status = {
					...status,
					[filename]: {
						error: $_('libraries.capabilities.imageLoadFailed', {
							default: "Couldn't load this image. It may have been removed."
						}),
						httpStatus: resp.status
					}
				};
				return;
			}
			const blob = await resp.blob();
			const blobUrl = URL.createObjectURL(blob);
			status = { ...status, [filename]: { blobUrl } };
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			status = { ...status, [filename]: { error: msg } };
		}
	}

	$effect(() => {
		if (key === trackedKey) return;
		trackedKey = key;

		// Revoke previously-loaded URLs.
		for (const k of Object.keys(status)) {
			const v = status[k];
			if (v && v.blobUrl) {
				try {
					URL.revokeObjectURL(v.blobUrl);
				} catch {
					/* ignore */
				}
			}
		}
		status = {};

		if (!lib || !itemId || images.length === 0) return;

		// Mark each filename as loading.
		const initial = {};
		for (const row of images) initial[row.filename] = {};
		status = initial;

		// Fire fetches.
		for (const row of images) {
			loadImage(row.filename);
		}
	});

	onDestroy(() => {
		for (const k of Object.keys(status)) {
			const v = status[k];
			if (v && v.blobUrl) {
				try {
					URL.revokeObjectURL(v.blobUrl);
				} catch {
					/* ignore */
				}
			}
		}
	});

	/** @type {ImageRow|null} */
	let enlarged = $state(null);
</script>

{#if images.length === 0}
	<p class="text-text-muted text-sm">
		{$_('libraries.capabilities.noImages', { default: 'No images available.' })}
	</p>
{:else}
	<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
		{#each images as img (img.filename)}
			{@const st = status[img.filename]}
			{@const blobUrl = st?.blobUrl || ''}
			{@const err = st?.error || ''}
			<button
				type="button"
				onclick={() => blobUrl && (enlarged = img)}
				disabled={!blobUrl}
				class="border-border bg-surface-muted hover:border-brand block overflow-hidden rounded-md border text-left transition-colors disabled:cursor-default"
				title={img.filename}
			>
				<div class="bg-surface-sunken flex aspect-square w-full items-center justify-center">
					{#if err}
						<div class="text-danger-text px-2 text-center text-xs">
							<div class="font-medium">{err}</div>
						</div>
					{:else if !blobUrl}
						<Loader2 class="text-text-subtle h-5 w-5 animate-spin" aria-hidden="true" />
					{:else}
						<img
							src={blobUrl}
							alt={img.filename}
							class="h-full w-full object-cover"
							loading="lazy"
						/>
					{/if}
				</div>
				<span class="text-text-muted block truncate px-2 py-1 text-xs">{img.filename}</span>
			</button>
		{/each}
	</div>

	{#if enlarged}
		{@const big = status[enlarged.filename]?.blobUrl || ''}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
			onclick={() => (enlarged = null)}
			role="presentation"
		>
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<img
				src={big}
				alt={enlarged.filename}
				class="max-h-[85vh] max-w-[85vw] rounded-lg shadow-2xl"
				onclick={(e) => e.stopPropagation()}
			/>
		</div>
	{/if}
{/if}
