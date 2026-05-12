<script>
	import { _, locale } from '$lib/i18n';

	// --- Props ---
	/**
	 * @typedef {Object} ModalBlocker
	 * @property {string} id - opaque id passed back to onRemoveBlocker
	 * @property {string} name - display name shown in the list
	 * @property {number|null} [contentCount] - total items inside the
	 *   referencing entity, rendered as "(N items)" when provided
	 * @property {boolean} [removing] - when true, the row's button shows
	 *   a spinner / disabled state
	 */

	let {
		isOpen = $bindable(false),
		isLoading = $bindable(false),
		error = $bindable(''),
		blockers = $bindable(/** @type {ModalBlocker[]} */ ([])),
		blockersTitle = '',
		blockerRemoveLabel = '',
		/** @type {(id: string) => void} */
		onRemoveBlocker = () => {},
		title = '',
		message = '',
		confirmText = '',
		cancelText = '',
		variant = 'danger', // 'danger' | 'warning' | 'info'
		// Hide the primary Confirm button (e.g. when the modal is opened in
		// "blocked" mode and the action is currently impossible).
		hideConfirm = false,
		onconfirm = () => {},
		oncancel = () => {}
	} = $props();

	// --- Locale Ready State (simplified pattern) ---
	// Uses $derived for reactive locale tracking - see $lib/utils/useLocaleReady.js
	let localeLoaded = $derived(!!$locale);

	// --- Computed values for variant styling ---
	/** @type {Record<string, {headerBg: string, headerBorder: string, iconColor: string, titleColor: string, confirmBg: string, confirmRing: string}>} */
	const variantStyles = {
		danger: {
			headerBg: 'bg-red-50',
			headerBorder: 'border-red-200',
			iconColor: 'text-red-600',
			titleColor: 'text-red-900',
			confirmBg: 'bg-red-600 hover:bg-red-700',
			confirmRing: 'focus:ring-red-500'
		},
		warning: {
			headerBg: 'bg-yellow-50',
			headerBorder: 'border-yellow-200',
			iconColor: 'text-yellow-600',
			titleColor: 'text-yellow-900',
			confirmBg: 'bg-yellow-600 hover:bg-yellow-700',
			confirmRing: 'focus:ring-yellow-500'
		},
		info: {
			headerBg: 'bg-blue-50',
			headerBorder: 'border-blue-200',
			iconColor: 'text-blue-600',
			titleColor: 'text-blue-900',
			confirmBg: 'bg-blue-600 hover:bg-blue-700',
			confirmRing: 'focus:ring-blue-500'
		}
	};

	let styles = $derived(variantStyles[variant] || variantStyles.danger);

	// --- Default text values ---
	let displayTitle = $derived(
		title || (localeLoaded ? $_('common.confirm', { default: 'Confirm' }) : 'Confirm')
	);
	let displayConfirmText = $derived(
		confirmText || (localeLoaded ? $_('common.confirm', { default: 'Confirm' }) : 'Confirm')
	);
	let displayCancelText = $derived(
		cancelText || (localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel')
	);

	// --- Functions ---
	function handleConfirm() {
		if (isLoading) return;
		onconfirm();
	}

	function handleCancel() {
		if (isLoading) return;
		oncancel();
		isOpen = false;
	}

	function handleOverlayClick() {
		if (isLoading) return;
		handleCancel();
	}

	/** @param {KeyboardEvent} event */
	function handleKeydown(event) {
		if (!isOpen) return;
		if (event.key === 'Escape') {
			handleCancel();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
	<!-- Modal Overlay -->
	<div
		class="fixed inset-0 z-40 bg-gray-500/75 transition-opacity"
		onclick={handleOverlayClick}
		aria-hidden="true"
	></div>

	<!-- Modal Panel -->
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
		<div
			class="relative mx-2 w-full max-w-md overflow-hidden rounded-lg border border-gray-300 bg-white shadow-xl"
			role="dialog"
			aria-modal="true"
			aria-labelledby="modal-title-confirm"
		>
			<!-- Modal Header -->
			<div
				class="flex items-center border-b px-4 py-3 sm:px-6 {styles.headerBg} {styles.headerBorder}"
			>
				{#if variant === 'danger'}
					<svg
						class="mr-2 h-6 w-6 {styles.iconColor}"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						aria-hidden="true"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
						/>
					</svg>
				{:else if variant === 'warning'}
					<svg
						class="mr-2 h-6 w-6 {styles.iconColor}"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						aria-hidden="true"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
						/>
					</svg>
				{:else}
					<svg
						class="mr-2 h-6 w-6 {styles.iconColor}"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						aria-hidden="true"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
						/>
					</svg>
				{/if}
				<h3 class="text-lg leading-6 font-medium {styles.titleColor}" id="modal-title-confirm">
					{displayTitle}
				</h3>
			</div>

			<!-- Modal Body -->
			<div class="px-4 py-5 sm:p-6">
				{#if message}
					<p class="text-sm break-words whitespace-pre-line text-gray-700">
						{message}
					</p>
				{/if}
				{#if error}
					<div
						class="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm break-words whitespace-pre-line text-red-700"
						role="alert"
					>
						{error}
					</div>
				{/if}
				{#if blockers && blockers.length > 0}
					<div class="mt-4 overflow-hidden rounded-md border border-gray-200 bg-gray-50">
						<div
							class="border-b border-gray-200 px-3 py-2 text-xs font-semibold tracking-wide text-gray-600 uppercase"
						>
							{blockersTitle ||
								(localeLoaded
									? $_('common.referencingItems', { default: 'Referenced by' })
									: 'Referenced by')}
						</div>
						<ul class="divide-y divide-gray-200 bg-white">
							{#each blockers as b (b.id)}
								<li class="flex items-center justify-between gap-3 px-3 py-2">
									<div class="min-w-0 flex-1">
										<p class="truncate text-sm font-medium text-gray-900" title={b.name}>
											{b.name}
										</p>
										{#if typeof b.contentCount === 'number'}
											<p class="text-xs text-gray-500">
												{b.contentCount}
												{localeLoaded ? $_('common.itemsLowercase', { default: 'items' }) : 'items'}
											</p>
										{/if}
									</div>
									<button
										type="button"
										onclick={() => onRemoveBlocker(b.id)}
										disabled={!!b.removing}
										class="inline-flex shrink-0 items-center gap-1 rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
									>
										{#if b.removing}
											<svg
												class="h-3 w-3 animate-spin"
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												aria-hidden="true"
											>
												<circle
													class="opacity-25"
													cx="12"
													cy="12"
													r="10"
													stroke="currentColor"
													stroke-width="4"
												/>
												<path
													class="opacity-75"
													fill="currentColor"
													d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
												/>
											</svg>
										{/if}
										{blockerRemoveLabel ||
											(localeLoaded ? $_('common.remove', { default: 'Remove' }) : 'Remove')}
									</button>
								</li>
							{/each}
						</ul>
					</div>
				{/if}
				{#if isLoading}
					<p class="mt-2 flex items-center text-sm text-gray-500">
						<svg
							class="mr-2 h-4 w-4 animate-spin"
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
						>
							<circle
								class="opacity-25"
								cx="12"
								cy="12"
								r="10"
								stroke="currentColor"
								stroke-width="4"
							></circle>
							<path
								class="opacity-75"
								fill="currentColor"
								d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
							></path>
						</svg>
						{localeLoaded ? $_('common.processing', { default: 'Processing...' }) : 'Processing...'}
					</p>
				{/if}
			</div>

			<!-- Modal Footer -->
			<div
				class="flex flex-col-reverse gap-2 border-t border-gray-200 bg-gray-50 px-4 py-3 sm:flex-row-reverse sm:px-6"
			>
				{#if !hideConfirm}
				<button
					type="button"
					class="inline-flex w-full justify-center rounded-md border border-transparent px-4 py-2 text-base font-medium text-white shadow-sm focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:opacity-50 sm:ml-3 sm:w-auto sm:text-sm {styles.confirmBg} {styles.confirmRing}"
					onclick={handleConfirm}
					disabled={isLoading}
					style="min-width:100px"
				>
					{#if isLoading}
						<svg
							class="mr-3 -ml-1 h-5 w-5 animate-spin text-white"
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
						>
							<circle
								class="opacity-25"
								cx="12"
								cy="12"
								r="10"
								stroke="currentColor"
								stroke-width="4"
							></circle>
							<path
								class="opacity-75"
								fill="currentColor"
								d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
							></path>
						</svg>
					{/if}
					{displayConfirmText}
				</button>
				{/if}
				<button
					type="button"
					class="focus:ring-brand inline-flex w-full justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:opacity-50 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
					onclick={handleCancel}
					disabled={isLoading}
					style="min-width:100px"
				>
					{displayCancelText}
				</button>
			</div>
		</div>
	</div>
{/if}
