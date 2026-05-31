<script>
	import { Upload, X, FileText } from 'lucide-svelte';
	import IconButton from './IconButton.svelte';

	/**
	 * Dropzone primitive — drag-drop + click-to-upload with file list.
	 *
	 * Owns its own queued-files state but exposes it via `files`
	 * ($bindable). Each item shows a per-row remove button.
	 *
	 * Callers wire submission outside of this component; the Dropzone is
	 * purely the staging UI.
	 */

	/**
	 * @typedef {Object} DropzoneProps
	 * @property {File[]} [files]            bindable list of staged files
	 * @property {boolean} [multiple]
	 * @property {string} [accept]           HTML accept attribute
	 * @property {string} [hint]             helper line under the dropzone
	 * @property {boolean} [disabled]
	 * @property {(files: File[]) => void} [onfiles]   called with the new merged list when files are added
	 * @property {(file: File, index: number) => void} [onremove]
	 * @property {string} [class]
	 * @property {string} [ariaLabel]
	 * @property {string} [title]            big call-to-action heading
	 * @property {string} [subtitle]         smaller line under the heading
	 * @property {string} [removeLabel]
	 */

	/** @type {DropzoneProps} */
	let {
		files = $bindable([]),
		multiple = true,
		accept = '',
		hint,
		disabled = false,
		onfiles,
		onremove,
		class: klass = '',
		ariaLabel = 'Upload files',
		title = 'Drop files here or click to upload',
		subtitle,
		removeLabel = 'Remove'
	} = $props();

	let dragging = $state(false);
	/** @type {HTMLInputElement | undefined} */
	let inputEl;

	function openPicker() {
		if (disabled) return;
		inputEl?.click();
	}

	function addFiles(/** @type {FileList | File[] | null} */ list) {
		if (!list) return;
		const incoming = Array.from(list);
		if (!incoming.length) return;
		const merged = multiple ? [...files, ...incoming] : [incoming[0]];
		files = merged;
		if (typeof onfiles === 'function') onfiles(merged);
	}

	/** @param {number} i */
	function removeAt(i) {
		const removed = files[i];
		const next = files.filter((/** @type {File} */ _, /** @type {number} */ idx) => idx !== i);
		files = next;
		if (typeof onremove === 'function') onremove(removed, i);
	}

	/** @param {DragEvent} e */
	function onDrop(e) {
		e.preventDefault();
		dragging = false;
		if (disabled) return;
		addFiles(e.dataTransfer?.files ?? null);
	}

	/** @param {DragEvent} e */
	function onDragOver(e) {
		e.preventDefault();
		if (!disabled) dragging = true;
	}

	/** @param {DragEvent} e */
	function onDragLeave(e) {
		if (e.currentTarget === e.target) {
			dragging = false;
		}
	}

	/** @param {Event} e */
	function onPick(e) {
		const input = /** @type {HTMLInputElement} */ (e.target);
		addFiles(input.files);
		// Clear so the same file can be re-selected later
		input.value = '';
	}

	/** @param {KeyboardEvent} e */
	function onKey(e) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			openPicker();
		}
	}

	/** @param {number} bytes */
	function fmtSize(bytes) {
		if (!bytes || bytes < 1024) return `${bytes ?? 0} B`;
		const units = ['KB', 'MB', 'GB'];
		let v = bytes / 1024;
		let i = 0;
		while (v >= 1024 && i < units.length - 1) {
			v /= 1024;
			i++;
		}
		return `${v.toFixed(1)} ${units[i]}`;
	}
</script>

<div class={klass}>
	<button
		type="button"
		aria-label={ariaLabel}
		{disabled}
		class="block w-full rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors focus:outline-none focus-visible:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-50 {dragging
			? 'border-brand bg-brand-subtle'
			: 'border-border-strong bg-surface-muted hover:border-brand hover:bg-brand-subtle/40'}"
		onclick={openPicker}
		onkeydown={onKey}
		ondrop={onDrop}
		ondragover={onDragOver}
		ondragleave={onDragLeave}
	>
		<div class="flex flex-col items-center gap-2">
			<div class="bg-surface-sunken text-text-muted rounded-full p-3">
				<Upload size={20} aria-hidden="true" />
			</div>
			<p class="type-body font-medium">{title}</p>
			{#if subtitle}
				<p class="type-caption">{subtitle}</p>
			{/if}
		</div>
		<input
			bind:this={inputEl}
			type="file"
			class="sr-only"
			{multiple}
			{accept}
			{disabled}
			onchange={onPick}
		/>
	</button>

	{#if hint}
		<p class="text-text-muted mt-2 text-xs">{hint}</p>
	{/if}

	{#if files.length > 0}
		<ul class="divide-border border-border bg-surface mt-3 divide-y rounded-md border">
			{#each files as f, i (`${f.name}-${i}`)}
				<li class="flex items-center justify-between gap-3 px-3 py-2">
					<div class="flex min-w-0 items-center gap-2">
						<FileText size={16} class="text-text-muted shrink-0" aria-hidden="true" />
						<div class="min-w-0">
							<p class="text-text truncate text-sm" title={f.name}>{f.name}</p>
							<p class="text-text-muted text-xs">{fmtSize(f.size)}</p>
						</div>
					</div>
					<IconButton
						icon={X}
						ariaLabel={removeLabel}
						tooltip={removeLabel}
						variant="danger-ghost"
						size="sm"
						onclick={() => removeAt(i)}
					/>
				</li>
			{/each}
		</ul>
	{/if}
</div>
